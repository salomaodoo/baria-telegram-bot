import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import logging
import time
from flask import Flask, request
import threading
import re

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuração do bot
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # https://seu-app.railway.app/webhook
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')  # production or development

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN não encontrado nas variáveis de ambiente")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Estados do usuário
class UserState:
    INITIAL = "initial"
    WAITING_NAME = "waiting_name"
    WAITING_AGE = "waiting_age"
    WAITING_GENDER = "waiting_gender"
    WAITING_HEIGHT = "waiting_height"
    WAITING_WEIGHT = "waiting_weight"
    WAITING_PATIENT_CONFIRMATION = "waiting_patient_confirmation"
    WAITING_RELATIONSHIP = "waiting_relationship"
    COMPLETED = "completed"
    GENERAL_CHAT = "general_chat"

# Armazenamento de dados do usuário (em produção, use um banco de dados)
user_sessions = {}

class UserData:
    def __init__(self):
        self.state = UserState.INITIAL
        self.name = ""
        self.age = ""
        self.gender = ""
        self.height = ""
        self.weight = ""
        self.is_patient = None
        self.relationship = ""
        self.last_activity = time.time()

def get_user_data(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = UserData()
    else:
        user_sessions[user_id].last_activity = time.time()
    return user_sessions[user_id]

def set_user_state(user_id, state):
    user_data = get_user_data(user_id)
    user_data.state = state
    logger.info(f"User {user_id} moved to state: {state}")

def cleanup_old_sessions():
    """Remove sessões antigas (mais de 1 hora)"""
    current_time = time.time()
    expired_users = []
    for user_id, user_data in user_sessions.items():
        if current_time - user_data.last_activity > 3600:  # 1 hora
            expired_users.append(user_id)
    
    for user_id in expired_users:
        del user_sessions[user_id]
        logger.info(f"Cleaned up session for user {user_id}")

def calculate_imc(weight, height):
    """Calcula o IMC com validação melhorada"""
    try:
        weight_kg = float(weight)
        height_m = float(height) / 100
        
        if weight_kg <= 0 or height_m <= 0:
            return None
            
        imc = weight_kg / (height_m ** 2)
        return round(imc, 2)
    except (ValueError, ZeroDivisionError):
        return None

def get_imc_classification(imc):
    """Classifica o IMC com mais detalhes"""
    if imc < 18.5:
        return "Baixo peso", "⚠️"
    elif imc < 25:
        return "Peso normal", "✅"
    elif imc < 30:
        return "Sobrepeso", "⚠️"
    elif imc < 35:
        return "Obesidade grau I", "🔶"
    elif imc < 40:
        return "Obesidade grau II", "🔸"
    else:
        return "Obesidade grau III (obesidade mórbida)", "🔴"

def get_ans_criteria_message(imc):
    """Retorna mensagem detalhada sobre critérios da ANS"""
    if imc >= 40:
        return """✅ **Você atende aos critérios da ANS para cirurgia bariátrica:**
• IMC ≥ 40 kg/m²
• Indicação para cirurgia bariátrica"""
    elif imc >= 35:
        return """⚠️ **Você pode atender aos critérios da ANS se tiver comorbidades:**
• IMC entre 35-39,9 kg/m²
• Necessárias comorbidades como: diabetes, hipertensão, apneia do sono, artrose, etc.
• Avaliação médica necessária"""
    else:
        return """❌ **Pelo IMC atual, você não atende aos critérios básicos da ANS:**
• IMC < 35 kg/m²
• Considere acompanhamento nutricional e exercícios
• Reavalie em consulta médica"""

def get_pathways_message():
    """Retorna informações detalhadas sobre caminhos"""
    return """🏥 **Caminhos para cirurgia bariátrica:**

🔹 **Particular:**
• Mais rápido (1-3 meses)
• Escolha livre do cirurgião
• Custo: R$ 15.000 a R$ 50.000
• Sem burocracia

🔹 **Plano de Saúde:**
• Cobertura obrigatória pela ANS
• Período de carência: 24 meses
• Avaliação multidisciplinar obrigatória
• Tempo médio: 6-12 meses

🔹 **SUS:**
• Totalmente gratuito
• Fila de espera: 1-3 anos
• Centros especializados (poucos)
• Avaliação rigorosa

📋 **Documentos necessários:**
• RG, CPF, comprovante de residência
• Cartão do SUS ou plano de saúde
• Histórico médico de tentativas de emagrecimento"""

# Melhor sistema de respostas automáticas
class ResponseEngine:
    def __init__(self):
        self.responses = {
            'dieta': {
                'keywords': ['dieta', 'alimentação', 'comer', 'comida', 'nutrição', 'cardápio', 'regime'],
                'response': """🥗 **Sobre alimentação pré e pós-cirúrgica:**

**Pré-operatório:**
• Dieta líquida 1-2 semanas antes
• Redução de carboidratos
• Aumento de proteínas
• Hidratação adequada

**Pós-operatório:**
• Fase 1: Líquidos (1-2 semanas)
• Fase 2: Pastosos (2-4 semanas)
• Fase 3: Sólidos macios (4-8 semanas)
• Fase 4: Alimentação normal (após 2 meses)

⚠️ **Importante:** Sempre siga as orientações do seu nutricionista!"""
            },
            'tecnicas': {
                'keywords': ['técnica', 'bypass', 'sleeve', 'banda', 'cirurgia', 'operação', 'procedimento'],
                'response': """🔬 **Principais técnicas cirúrgicas:**

**Sleeve (Manga Gástrica):**
• Remove 80% do estômago
• Mais simples e rápida
• Menor risco de complicações

**Bypass Gástrico:**
• Reduz estômago + desvia intestino
• Maior perda de peso
• Mais complexa

**Banda Gástrica:**
• Anel ajustável no estômago
• Reversível
• Menos eficaz a longo prazo

👨‍⚕️ **A escolha da técnica depende de:**
• Seu IMC e comorbidades
• Histórico médico
• Preferência do cirurgião
• Avaliação individual"""
            },
            'recuperacao': {
                'keywords': ['recuperação', 'pós-operatório', 'depois', 'cicatrização', 'volta', 'trabalho'],
                'response': """🏥 **Recuperação pós-cirúrgica:**

**Primeiros dias:**
• Internação: 1-3 dias
• Repouso absoluto
• Dieta líquida
• Medicação para dor

**Primeira semana:**
• Repouso relativo
• Caminhadas leves
• Curativos diários
• Acompanhamento médico

**Primeiro mês:**
• Volta gradual às atividades
• Exercícios leves
• Dieta pastosa
• Consultas semanais

**Após 2 meses:**
• Volta ao trabalho (se escritório)
• Exercícios moderados
• Alimentação normal
• Acompanhamento mensal

⚠️ **Complicações possíveis:**
• Náuseas e vômitos
• Dumping syndrome
• Deficiências nutricionais
• Necessidade de suplementação"""
            },
            'custos': {
                'keywords': ['custo', 'preço', 'valor', 'quanto custa', 'dinheiro', 'pagar'],
                'response': """💰 **Custos da cirurgia bariátrica:**

**Cirurgia Particular:**
• Sleeve: R$ 15.000 - R$ 25.000
• Bypass: R$ 20.000 - R$ 35.000
• Banda: R$ 12.000 - R$ 20.000

**Custos adicionais:**
• Exames pré-operatórios: R$ 2.000 - R$ 5.000
• Internação: R$ 3.000 - R$ 8.000
• Acompanhamento: R$ 2.000 - R$ 5.000/ano

**Formas de pagamento:**
• À vista (desconto 10-20%)
• Parcelado (até 24x)
• Financiamento médico
• Consórcio

💡 **Dica:** Compare preços e busque referências do cirurgião!"""
            },
            'tempo': {
                'keywords': ['tempo', 'quanto demora', 'duração', 'prazo', 'espera'],
                'response': """⏰ **Tempo para cirurgia bariátrica:**

**Particular:**
• Consulta inicial → Cirurgia: 1-3 meses
• Depende dos exames e preparação

**Plano de Saúde:**
• Após carência: 6-12 meses
• Avaliação multidisciplinar obrigatória
• Pode haver recursos e negativas

**SUS:**
• Fila de espera: 1-3 anos
• Varia muito por região
• Poucos centros especializados

**Duração da cirurgia:**
• Sleeve: 1-2 horas
• Bypass: 2-3 horas
• Laparoscópica (preferível)

⏱️ **Prepare-se:** Use o tempo de espera para mudanças de hábitos!"""
            }
        }
    
    def get_response(self, text, user_name=""):
        text_lower = text.lower()
        
        for category, data in self.responses.items():
            if any(keyword in text_lower for keyword in data['keywords']):
                return data['response']
        
        # Resposta padrão mais inteligente
        return f"""💙 Oi{f', {user_name}' if user_name else ''}! 

Estou aqui para ajudar com dúvidas sobre cirurgia bariátrica. Posso falar sobre:

• 🥗 **Dieta** (pré e pós-operatório)
• 🔬 **Técnicas** cirúrgicas 
• 🏥 **Recuperação** e cuidados
• 💰 **Custos** e formas de pagamento
• ⏰ **Tempo** de espera
• 📋 **Documentos** necessários

Sobre o que você gostaria de saber mais?"""

response_engine = ResponseEngine()

# Configuração Flask
@app.route('/')
def home():
    return {
        "status": "BarIA Bot está rodando!",
        "bot_info": "Assistente virtual para cirurgia bariátrica",
        "version": "2.0",
        "environment": ENVIRONMENT
    }

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data(as_text=True)
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "ERROR", 500

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": time.time()}

# Handlers melhorados
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data.state = UserState.INITIAL
    
    # Limpar sessões antigas
    cleanup_old_sessions()
    
    username = message.from_user.first_name or "amigo(a)"
    
    response = f"""Olá, {username}! 👋 

Eu sou a **BarIA**, sua assistente virtual especializada em cirurgia bariátrica no Brasil.

Posso te ajudar com:
• Cálculo de IMC e análise
• Critérios da ANS
• Caminhos para cirurgia
• Dúvidas sobre procedimentos
• Orientações gerais

Como posso te ajudar hoje?"""
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📊 Fazer avaliação completa", callback_data="start_questions"),
        InlineKeyboardButton("💬 Só quero conversar", callback_data="general_chat"),
        InlineKeyboardButton("📋 Ver comandos", callback_data="help")
    )
    
    bot.send_message(message.chat.id, response, reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = """🤖 **Comandos disponíveis:**

• `/start` - Iniciar conversa
• `/help` - Ver esta ajuda
• `/reset` - Recomeçar avaliação

**Posso falar sobre:**
• Dieta pré e pós-operatório
• Técnicas cirúrgicas
• Recuperação e cuidados
• Custos e formas de pagamento
• Tempo de espera
• Critérios da ANS

Digite qualquer dúvida que eu respondo! 💙"""
    
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['reset'])
def handle_reset(message):
    user_id = message.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    bot.send_message(message.chat.id, "✅ Dados resetados! Digite /start para começar novamente.")

# Callback handlers
@bot.callback_query_handler(func=lambda call: call.data == "start_questions")
def start_questions(call):
    user_id = call.from_user.id
    set_user_state(user_id, UserState.WAITING_NAME)
    
    bot.edit_message_text(
        "📝 **Vamos começar sua avaliação!**\n\n1️⃣ Qual é o seu primeiro nome?",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == "general_chat")
def general_chat(call):
    user_id = call.from_user.id
    set_user_state(user_id, UserState.GENERAL_CHAT)
    
    bot.edit_message_text(
        "💬 **Perfeito!** Estou aqui para tirar suas dúvidas sobre cirurgia bariátrica.\n\nPode me perguntar qualquer coisa! 💙",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == "help")
def help_callback(call):
    handle_help(call.message)

# Handler principal de mensagens
@bot.message_handler(func=lambda message: True)
def handle_text_message(message):
    try:
        user_id = message.from_user.id
        user_data = get_user_data(user_id)
        text = message.text.strip()
        
        # Log da mensagem
        logger.info(f"User {user_id} ({user_data.state}): {text}")
        
        # Saudações iniciais
        if text.lower() in ['olá', 'oi', 'hello', 'hey', 'bom dia', 'boa tarde', 'boa noite']:
            if user_data.state == UserState.INITIAL:
                handle_start(message)
                return
        
        # Fluxo de coleta de dados
        if user_data.state == UserState.WAITING_NAME:
            handle_name_input(message, user_data)
        elif user_data.state == UserState.WAITING_PATIENT_CONFIRMATION:
            handle_patient_confirmation(message, user_data)
        elif user_data.state == UserState.WAITING_RELATIONSHIP:
            handle_relationship_input(message, user_data)
        elif user_data.state == UserState.WAITING_AGE:
            handle_age_input(message, user_data)
        elif user_data.state == UserState.WAITING_GENDER:
            handle_gender_input(message, user_data)
        elif user_data.state == UserState.WAITING_HEIGHT:
            handle_height_input(message, user_data)
        elif user_data.state == UserState.WAITING_WEIGHT:
            handle_weight_input(message, user_data)
        elif user_data.state == UserState.GENERAL_CHAT or user_data.state == UserState.COMPLETED:
            handle_general_question(message, user_data)
        else:
            bot.reply_to(message, "❌ Algo deu errado. Digite /start para começar novamente.")
    
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        bot.reply_to(message, "❌ Ocorreu um erro. Tente novamente ou digite /start.")

def handle_name_input(message, user_data):
    name = message.text.strip()
    
    # Validação básica do nome
    if len(name) < 2 or len(name) > 50:
        bot.reply_to(message, "❌ Por favor, digite um nome válido (entre 2 e 50 caracteres).")
        return
    
    # Limpar caracteres especiais
    name = re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', name).title()
    
    user_data.name = name
    set_user_state(message.from_user.id, UserState.WAITING_PATIENT_CONFIRMATION)
    
    bot.reply_to(message, 
        f"Obrigada, **{user_data.name}**! 😊\n\n2️⃣ Você é a pessoa interessada na cirurgia bariátrica, ou está buscando informações para auxiliar outra pessoa?",
        parse_mode='Markdown'
    )

def handle_patient_confirmation(message, user_data):
    text = message.text.lower().strip()
    
    if any(word in text for word in ['sim', 'sou', 'eu', 'própria', 'mesmo', 'para mim', 'minha', 'meu']):
        user_data.is_patient = True
        set_user_state(message.from_user.id, UserState.WAITING_AGE)
        bot.reply_to(message, 
            f"Perfeito, **{user_data.name}**! Vamos continuar sua avaliação.\n\n3️⃣ Qual é a sua idade?",
            parse_mode='Markdown'
        )
    
    elif any(word in text for word in ['não', 'nao', 'outra', 'outra pessoa', 'alguém', 'familiar', 'parente']):
        user_data.is_patient = False
        set_user_state(message.from_user.id, UserState.WAITING_RELATIONSHIP)
        bot.reply_to(message, 
            f"Entendi, **{user_data.name}**. É muito importante o apoio da família! 👨‍👩‍👧‍👦\n\n3️⃣ Qual é o seu grau de parentesco com a pessoa interessada?",
            parse_mode='Markdown'
        )
    
    else:
        bot.reply_to(message, "❓ Por favor, me diga se **você** é a pessoa interessada na cirurgia ou se está buscando informações para **auxiliar outra pessoa**.")

def handle_relationship_input(message, user_data):
    user_data.relationship = message.text.strip()
    
    message_text = f"""Obrigada pela informação, **{user_data.name}**! 

💙 **Orientações importantes sobre apoio familiar:**

• ✅ As orientações médicas devem sempre ser direcionadas pelos profissionais
• ✅ A decisão final é sempre da pessoa interessada
• ❌ Não force ou pressione procedimentos cirúrgicos
• 💪 Seu papel é oferecer apoio emocional e acompanhamento

**📄 Documentos que podem ser necessários:**
• RG e CPF
• Cartão do SUS ou plano de saúde
• Comprovante de residência
• Exames médicos (serão solicitados pelo cirurgião)

Posso continuar te ajudando com orientações gerais sobre o processo. É só me perguntar! 💙"""
    
    set_user_state(message.from_user.id, UserState.COMPLETED)
    bot.reply_to(message, message_text, parse_mode='Markdown')

def handle_age_input(message, user_data):
    try:
        age = int(message.text.strip())
        if age < 16:
            bot.reply_to(message, "❌ A cirurgia bariátrica é recomendada apenas para pessoas com 16 anos ou mais.")
            return
        elif age > 100:
            bot.reply_to(message, "❌ Por favor, digite uma idade válida.")
            return
        
        user_data.age = str(age)
        set_user_state(message.from_user.id, UserState.WAITING_GENDER)
        
        bot.reply_to(message, 
            f"Obrigada, **{user_data.name}**! 😊\n\n4️⃣ Qual é o seu gênero?\n\n• Masculino\n• Feminino\n• Outro",
            parse_mode='Markdown'
        )
    
    except ValueError:
        bot.reply_to(message, "❌ Por favor, digite apenas números para a idade (ex: 25).")

def handle_gender_input(message, user_data):
    gender = message.text.strip().lower()
    
    if gender in ['masculino', 'homem', 'macho', 'm', 'male']:
        user_data.gender = 'masculino'
    elif gender in ['feminino', 'mulher', 'fêmea', 'f', 'female']:
        user_data.gender = 'feminino'
    elif gender in ['outro', 'outros', 'não-binário', 'nao-binario', 'nb', 'non-binary']:
        user_data.gender = 'outro'
    else:
        bot.reply_to(message, "❌ Por favor, escolha: **masculino**, **feminino** ou **outro**.")
        return
    
    set_user_state(message.from_user.id, UserState.WAITING_HEIGHT)
    bot.reply_to(message, 
        f"Obrigada, **{user_data.name}**! 😊\n\n5️⃣ Qual é a sua altura?\n\n📏 Digite em centímetros (ex: **170**)",
        parse_mode='Markdown'
    )

def handle_height_input(message, user_data):
    try:
        height_text = message.text.strip().replace(',', '.')
        height = float(height_text)
        
        if height < 100 or height > 250:
            bot.reply_to(message, "❌ Por favor, digite uma altura válida em centímetros (ex: **170**).")
            return
        
        user_data.height = str(height)
        set_user_state(message.from_user.id, UserState.WAITING_WEIGHT)
        
        bot.reply_to(message, 
            f"Obrigada, **{user_data.name}**! 😊\n\n6️⃣ Qual é o seu peso atual?\n\n⚖️ Digite em quilos (ex: **85**)",
            parse_mode='Markdown'
        )
    
    except ValueError:
        bot.reply_to(message, "❌ Por favor, digite apenas números para a altura (ex: **170**).")

def handle_weight_input(message, user_data):
    try:
        weight_text = message.text.strip().replace(',', '.')
        weight = float(weight_text)
        
        if weight < 30 or weight > 300:
            bot.reply_to(message, "❌ Por favor, digite um peso válido em quilos (ex: **85**).")
            return
        
        user_data.weight = str(weight)
        set_user_state(message.from_user.id, UserState.COMPLETED)
        
        # Calcular IMC e enviar relatório completo
        send_complete_report(message, user_data)
    
    except ValueError:
        bot.reply_to(message, "❌ Por favor, digite apenas números para o peso (ex: **85**).")

def send_complete_report(message, user_data):
    imc = calculate_imc(user_data.weight, user_data.height)
    
    if imc is None:
        bot.reply_to(message, "❌ Erro ao calcular IMC. Verifique os dados e tente novamente.")
        return
    
    classification, icon = get_imc_classification(imc)
    ans_criteria = get_ans_criteria_message(imc)
    pathways = get_pathways_message()
    
    report = f"""✅ **Análise completa - {user_data.name}**

📊 **Seus dados:**
• **Nome:** {user_data.name}
• **Idade:** {user_data.age} anos
• **Altura:** {user_data.height} cm
• **Peso:** {user_data.weight} kg

🔢 **IMC:** {imc} kg/m²
{icon} **Classificação:** {classification}

{ans_criteria}

{pathways}

💡 **Próximos passos recomendados:**
1. ✅ Consulte um cirurgião bariátrico qualificado
2. ✅ Realize avaliação multidisciplinar completa
3. ✅ Faça todos os exames pré-operatórios
4. ✅ Prepare-se psicologicamente para a mudança

Posso continuar te ajudando com dúvidas específicas! É só me perguntar. 💙"""
    
    bot.reply_to(message, report, parse_mode='Markdown')

def handle_general_question(message, user_data):
    """Sistema melhorado de respostas"""
    text = message.text.strip()
    
    # Obter resposta do sistema inteligente
    response = response_engine.get_response(text, user_data.name)
    
    bot.reply_to(message, response, parse_mode='Markdown')

# Handlers de erro
@bot.message_handler(func=lambda message: True, content_types=['photo', 'video', 'document', 'audio', 'voice'])
def handle_media(message):
    bot.reply_to(message, 
        "📎 Obrigada pelo arquivo! No momento, trabalho apenas com mensagens de texto.\n\nComo posso te ajudar com suas dúvidas sobre cirurgia bariátrica? 💙"
    )

def setup_webhook():
    """Configura webhook para produção"""
    if ENVIRONMENT == 'production' and WEBHOOK_URL:
        try:
            bot.remove_webhook()
            bot.set_webhook(url=WEBHOOK_URL)
            logger.info(f"Webhook configurado: {WEBHOOK_URL}")
        except Exception as e:
            logger.error(f"Erro ao configurar webhook: {e}")

def run_bot():
    """Executa o bot"""
    logger.info("🤖 BarIA iniciada! Bot rodando...")
    
    if ENVIRONMENT == 'production':
        setup_webhook()
    else:
        # Desenvolvimento - usar polling
        bot.remove_webhook()
        bot.infinity_polling()

# Inicialização
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    
    if ENVIRONMENT == 'production':
        # Produção - webhook
        setup_webhook()
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # Desenvolvimento - polling + Flask
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()
        app.run(host='0.0.0.0', port=port, debug=True)
