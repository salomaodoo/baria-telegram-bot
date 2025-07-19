import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import logging
import time
from flask import Flask, request
import threading
import re
import requests
import json

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuração do bot
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')  # Corrigido: GROQ não GROK
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # https://seu-app.railway.app/webhook
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')  # production or development

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN não encontrado nas variáveis de ambiente")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
app = Flask(__name__)

# Estados do usuário
class UserState:
    INITIAL = "initial"
    WAITING_CONSENT = "waiting_consent"
    WAITING_NAME = "waiting_name"
    WAITING_PATIENT_CONFIRMATION = "waiting_patient_confirmation"
    WAITING_RELATIONSHIP = "waiting_relationship"
    WAITING_AGE = "waiting_age"
    WAITING_GENDER = "waiting_gender"
    WAITING_HEIGHT = "waiting_height"
    WAITING_WEIGHT = "waiting_weight"
    COMPLETED = "completed"
    HELPER_COMPLETED = "helper_completed"
    GENERAL_CHAT = "general_chat"
    QUICK_IMC_HEIGHT = "quick_imc_height"
    QUICK_IMC_WEIGHT = "quick_imc_weight"

# Armazenamento de dados do usuário
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
        self.conversation_history = []

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

def create_gender_keyboard():
    """Cria teclado inline para seleção de gênero"""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("👨 Masculino", callback_data="gender_masculino"),
        InlineKeyboardButton("👩 Feminino", callback_data="gender_feminino")
    )
    markup.row(InlineKeyboardButton("⚧ Outro", callback_data="gender_outro"))
    return markup

def create_main_menu():
    """Cria menu principal de opções"""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📋 Critérios ANS", callback_data="criterios"),
        InlineKeyboardButton("📄 Documentos", callback_data="documentos")
    )
    markup.row(
        InlineKeyboardButton("🏥 Caminhos", callback_data="caminhos"),
        InlineKeyboardButton("🧮 Calcular IMC", callback_data="calc_imc")
    )
    markup.row(
        InlineKeyboardButton("💬 Fazer pergunta", callback_data="pergunta")
    )
    return markup

def ask_grok(question, user_data=None):
    """Integração com Groq Cloud AI"""
    if not GROQ_API_KEY:
        return "Desculpe, a IA não está disponível no momento. Posso ajudar com informações básicas sobre cirurgia bariátrica!"
    
    try:
        # Contexto personalizado para cirurgia bariátrica
        context = """Você é BarIA, uma assistente virtual especializada em cirurgia bariátrica no Brasil. 
        Você deve ser amigável, empática e dar informações gerais sobre o processo.
        
        IMPORTANTE: 
        - Não forneça valores/preços específicos
        - Não dê tempos exatos de cirurgia
        - Não detalhe procedimentos cirúrgicos específicos
        - Sempre recomende consultar profissionais habilitados para detalhes técnicos
        - Seja calorosa e humana nas respostas
        - Use linguagem simples e acessível
        
        Informações do usuário:"""
        
        if user_data and user_data.name:
            context += f"\n- Nome: {user_data.name}"
        if user_data and user_data.age:
            context += f"\n- Idade: {user_data.age} anos"
        if user_data and user_data.is_patient is not None:
            context += f"\n- É paciente: {'Sim' if user_data.is_patient else 'Não'}"
        
        # Preparar histórico de conversa
        messages = [
            {"role": "system", "content": context},
        ]
        
        # Adicionar histórico recente (últimas 5 mensagens)
        if user_data and user_data.conversation_history:
            for msg in user_data.conversation_history[-5:]:
                messages.append(msg)
        
        messages.append({"role": "user", "content": question})
        
        # Fazer chamada para Groq Cloud
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            # Atualizar histórico
            if user_data:
                user_data.conversation_history.append({"role": "user", "content": question})
                user_data.conversation_history.append({"role": "assistant", "content": ai_response})
                # Manter apenas últimas 10 mensagens
                if len(user_data.conversation_history) > 10:
                    user_data.conversation_history = user_data.conversation_history[-10:]
            
            return ai_response
        else:
            logger.error(f"Groq API error: {response.status_code} - {response.text}")
            return "Desculpe, tive um probleminha técnico. Pode tentar novamente?"
    
    except Exception as e:
        logger.error(f"Error calling Groq API: {e}")
        return "Ops! Algo deu errado. Posso tentar responder de outra forma ou você pode perguntar novamente!"

def calculate_imc(weight, height):
    """Calcula o IMC com validação"""
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
    """Classifica o IMC"""
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
        return "Obesidade grau III", "🔴"

def get_pathways_message():
    """Retorna informações sobre caminhos"""
    return """🏥 <b>Caminhos para cirurgia bariátrica:</b>

🔹 <b>Particular:</b>
• Consulte diretamente com cirurgiões especializados
• Para informações sobre custos, consulte profissionais habilitados

🔹 <b>Plano de Saúde:</b>
• Cobertura obrigatória pela ANS
• Período de carência: 24 meses
• Consulte seu plano para prazos específicos

🔹 <b>SUS:</b>
• Totalmente gratuito
• Consulte unidades de saúde para informações sobre fila de espera

📋 <b>Documentos necessários:</b>
• RG, CPF, comprovante de residência
• Cartão do SUS ou plano de saúde
• Histórico médico"""

def is_restricted_question(text):
    """Verifica se a pergunta contém temas restritos"""
    restricted_keywords = [
        # Valores e custos
        'valor', 'preço', 'custo', 'quanto custa', 'preço da cirurgia',
        'quanto paga', 'valor da operação', 'preço do procedimento',
        
        # Tempos específicos de cirurgia
        'tempo de cirurgia', 'duração da cirurgia', 'quantas horas',
        'tempo de operação', 'duração do procedimento',
        
        # Métodos cirúrgicos específicos
        'laparoscopia', 'laparoscópica', 'método cirúrgico',
        'como é feita', 'como fazem', 'procedimento cirúrgico',
        'técnica cirúrgica', 'como operam', 'cortes', 'incisões'
    ]
    
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in restricted_keywords)

def get_restriction_message():
    """Retorna mensagem padrão para temas restritos"""
    return """⚠️ <b>Informação restrita</b>

Para informações sobre valores, tempos de cirurgia e métodos cirúrgicos específicos, você deve consultar diretamente com:

• Cirurgiões especializados
• Hospitais credenciados
• Seu plano de saúde
• Unidades do SUS

Posso ajudar com outras dúvidas sobre critérios da ANS e documentação necessária! 💙"""

def get_gendered_message(name, gender):
    """Retorna mensagem com gênero apropriado"""
    if gender == "outro":
        return f"Obrigada, {name}! 😊"
    elif gender == "feminino":
        return f"Obrigada, {name}! 😊"
    else:  # masculino
        return f"Obrigado, {name}! 😊"

# Configuração Flask
@app.route('/')
def home():
    return {
        "status": "BarIA Bot está rodando!",
        "bot_info": "Assistente virtual para cirurgia bariátrica",
        "version": "3.0",
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

# Handlers
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data.state = UserState.INITIAL
    
    cleanup_old_sessions()
    
    response = """Olá! 👋 Eu sou a BarIA, sua assistente virtual focada em cirurgia bariátrica no Brasil. 

Posso te fazer algumas perguntinhas para entender melhor sua situação e te ajudar nessa jornada? Ou se preferir, pode me fazer qualquer pergunta sobre o assunto!"""
    
    set_user_state(user_id, UserState.WAITING_CONSENT)
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['criterios', 'documentos', 'caminhos', 'orientacoes'])
def handle_custom_commands(message):
    command = message.text.lower().strip()
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    
    if command == '/criterios':
        response = """📋 <b>Critérios da ANS para cirurgia bariátrica:</b>

✅ <b>Critérios obrigatórios:</b>
• IMC ≥ 40 kg/m² OU
• IMC ≥ 35 kg/m² + comorbidades (diabetes, hipertensão, apneia do sono, etc.)
• Idade entre 16 e 65 anos
• Tentativas de tratamento clínico sem sucesso por pelo menos 2 anos

⚠️ <b>Observações importantes:</b>
• Avaliação médica multidisciplinar obrigatória
• Acompanhamento psicológico necessário
• Carência de 24 meses no plano de saúde

Para avaliação individual, consulte um cirurgião especialista! 💙"""
    
    elif command == '/documentos':
        response = """📄 <b>Documentos necessários:</b>

🔹 <b>Documentos pessoais:</b>
• RG e CPF
• Comprovante de residência atualizado
• Cartão do SUS ou carteira do plano de saúde

🔹 <b>Documentos médicos:</b>
• Histórico médico completo
• Exames anteriores (se houver)
• Relatórios de tentativas de tratamento clínico
• Comprovação de comorbidades (se aplicável)

🔹 <b>Para planos de saúde:</b>
• Declaração de carência cumprida
• Guia de solicitação de procedimento

Consulte sempre com o local onde fará o procedimento para lista completa! 💙"""
    
    elif command == '/caminhos':
        response = get_pathways_message()
    
    elif command == '/orientacoes':
        response = """💡 <b>Orientações gerais:</b>

🔹 <b>Antes da cirurgia:</b>
• Consulte cirurgião especialista
• Faça avaliação multidisciplinar
• Prepare-se psicologicamente
• Organize documentação

🔹 <b>Pós-operatório:</b>
• Siga rigorosamente as orientações médicas
• Mantenha acompanhamento nutricional
• Realize atividade física conforme orientação
• Participe de grupos de apoio

🔹 <b>Dicas importantes:</b>
• Não tome decisões por impulso
• Busque informações em fontes confiáveis
• Conte com apoio familiar
• Tenha paciência com o processo

Outras dúvidas específicas? 💙"""
    
    markup = create_main_menu()
    bot.send_message(message.chat.id, response, reply_markup=markup)

@bot.message_handler(commands=['reset'])
def handle_reset(message):
    user_id = message.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    bot.send_message(message.chat.id, "✅ Dados resetados! Digite /start para começar novamente.")

# Handler de callback queries
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        user_id = call.from_user.id
        user_data = get_user_data(user_id)
        
        # Callbacks de gênero
        if call.data.startswith("gender_"):
            gender = call.data.split("_")[1]
            if gender == "masculino":
                user_data.gender = "masculino"
                response_msg = f"Obrigado, {user_data.name}! 😊"
            elif gender == "feminino":
                user_data.gender = "feminino"
                response_msg = f"Obrigada, {user_data.name}! 😊"
            else:  # outro
                user_data.gender = "outro"
                response_msg = f"Obrigada, {user_data.name}! 😊"
            
            set_user_state(user_id, UserState.WAITING_HEIGHT)
            bot.edit_message_text(
                f"{response_msg}\n\n5️⃣ Qual é a sua altura? (exemplo: 170 cm)",
                call.message.chat.id,
                call.message.message_id
            )
        
        # Callbacks do menu principal
        elif call.data == "criterios":
            response = """📋 <b>Critérios da ANS para cirurgia bariátrica:</b>

✅ <b>Critérios obrigatórios:</b>
• IMC ≥ 40 kg/m² OU
• IMC ≥ 35 kg/m² + comorbidades
• Idade entre 16 e 65 anos
• Tentativas de tratamento clínico por 2+ anos

Para avaliação individual, consulte um especialista! 💙"""
            
        elif call.data == "documentos":
            response = """📄 <b>Documentos necessários:</b>

🔹 <b>Pessoais:</b> RG, CPF, comprovante residência
🔹 <b>Médicos:</b> Histórico médico, exames
🔹 <b>Plano:</b> Carteira, guia de solicitação

Consulte sempre o local do procedimento! 💙"""
            
        elif call.data == "caminhos":
            response = get_pathways_message()
            
        elif call.data == "calc_imc":
            set_user_state(user_id, UserState.QUICK_IMC_HEIGHT)
            response = "🧮 <b>Calculadora de IMC</b>\n\n1️⃣ Digite sua altura em centímetros (exemplo: 170):"
            
        elif call.data == "pergunta":
            set_user_state(user_id, UserState.GENERAL_CHAT)
            response = "💬 <b>Perguntas e Respostas</b>\n\nFaça sua pergunta sobre cirurgia bariátrica e eu te ajudo! 😊"
        
        else:
            response = "Opção não reconhecida."
        
        # Responder callback
        bot.answer_callback_query(call.id)
        
        # Enviar resposta se não for callback de gênero
        if not call.data.startswith("gender_"):
            markup = create_main_menu() if call.data != "pergunta" else None
            bot.send_message(call.message.chat.id, response, reply_markup=markup)
            
    except Exception as e:
        logger.error(f"Error handling callback: {e}")
        bot.answer_callback_query(call.id, "Erro interno. Tente novamente.")

# Handler principal de mensagens
@bot.message_handler(func=lambda message: True)
def handle_text_message(message):
    try:
        user_id = message.from_user.id
        user_data = get_user_data(user_id)
        text = message.text.strip()
        
        logger.info(f"User {user_id} ({user_data.state}): {text}")
        
        # Verificar se é uma pergunta restrita em qualquer estado
        if is_restricted_question(text):
            markup = create_main_menu()
            bot.reply_to(message, get_restriction_message(), reply_markup=markup)
            return
        
        # Saudações iniciais
        if text.lower() in ['olá', 'oi', 'hello', 'hey', 'bom dia', 'boa tarde', 'boa noite']:
            if user_data.state == UserState.INITIAL:
                handle_start(message)
                return
        
        # Roteamento por estado
        if user_data.state == UserState.WAITING_CONSENT:
            handle_consent(message, user_data)
        elif user_data.state == UserState.WAITING_NAME:
            handle_name_input(message, user_data)
        elif user_data.state == UserState.WAITING_PATIENT_CONFIRMATION:
            handle_patient_confirmation(message, user_data)
        elif user_data.state == UserState.WAITING_RELATIONSHIP:
            handle_relationship_input(message, user_data)
        elif user_data.state == UserState.WAITING_AGE:
            handle_age_input(message, user_data)
        elif user_data.state == UserState.WAITING_GENDER:
            handle_gender_input_text(message, user_data)
        elif user_data.state == UserState.WAITING_HEIGHT:
            handle_height_input(message, user_data)
        elif user_data.state == UserState.WAITING_WEIGHT:
            handle_weight_input(message, user_data)
        elif user_data.state == UserState.QUICK_IMC_HEIGHT:
            handle_quick_imc_height(message, user_data)
        elif user_data.state == UserState.QUICK_IMC_WEIGHT:
            handle_quick_imc_weight(message, user_data)
        elif user_data.state in [UserState.COMPLETED, UserState.HELPER_COMPLETED, UserState.GENERAL_CHAT]:
            handle_general_question(message, user_data)
        else:
            markup = create_main_menu()
            bot.reply_to(message, "❌ Algo deu errado. Escolha uma opção:", reply_markup=markup)
    
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        markup = create_main_menu()
        bot.reply_to(message, "❌ Ocorreu um erro. Tente novamente:", reply_markup=markup)

# Funções de handler individuais
def handle_consent(message, user_data):
    text = message.text.lower().strip()
    
    if any(word in text for word in ['sim', 'claro', 'ok', 'pode', 'vamos', 'aceito']):
        set_user_state(message.from_user.id, UserState.WAITING_NAME)
        bot.reply_to(message, "Que bom! Vamos começar então 😊\n\n1️⃣ Qual é o seu primeiro nome?")
    elif any(word in text for word in ['não', 'nao', 'agora não', 'depois']):
        set_user_state(message.from_user.id, UserState.GENERAL_CHAT)
        markup = create_main_menu()
        bot.reply_to(message, "Sem problemas! Fico aqui para tirar suas dúvidas sobre cirurgia bariátrica. 💙", reply_markup=markup)
    else:
        ai_response = ask_grok(f"O usuário disse: '{message.text}'. Ele estava sendo perguntado se queria responder algumas perguntas para receber orientações personalizadas. Responda de forma amigável pedindo uma confirmação mais clara.", user_data)
        bot.reply_to(message, ai_response)

def handle_name_input(message, user_data):
    name = message.text.strip()
    
    if len(name) < 2 or len(name) > 50:
        bot.reply_to(message, "Hmm, esse nome parece estar incompleto. Pode me dizer seu primeiro nome?")
        return
    
    name = re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', name).title()
    user_data.name = name
    set_user_state(message.from_user.id, UserState.WAITING_PATIENT_CONFIRMATION)
    
    bot.reply_to(message, f"Prazer te conhecer, {user_data.name}! 😊\n\n2️⃣ Você é a pessoa interessada na cirurgia bariátrica?")

def handle_patient_confirmation(message, user_data):
    text = message.text.lower().strip()
    
    if any(word in text for word in ['sim', 'sou', 'eu', 'própria', 'mesmo']):
        user_data.is_patient = True
        set_user_state(message.from_user.id, UserState.WAITING_AGE)
        bot.reply_to(message, f"Perfeito, {user_data.name}! Vou te ajudar da melhor forma possível 💙\n\n3️⃣ Qual é a sua idade?")
    
    elif any(word in text for word in ['não', 'nao', 'outra', 'alguém']):
        user_data.is_patient = False
        set_user_state(message.from_user.id, UserState.WAITING_RELATIONSHIP)
        bot.reply_to(message, f"Entendi, {user_data.name}. Que legal você estar apoiando essa pessoa! 💙\n\n3️⃣ Qual é o seu grau de parentesco com a pessoa interessada?")
    
    else:
        ai_response = ask_grok(f"O usuário disse: '{message.text}'. Ele estava sendo perguntado se era a pessoa interessada na cirurgia bariátrica. Responda de forma amigável pedindo esclarecimento.", user_data)
        bot.reply_to(message, ai_response)

def handle_relationship_input(message, user_data):
    user_data.relationship = message.text.strip()
    
    response = f"""Que bom saber, {user_data.name}! 

💙 <b>Sobre o apoio familiar:</b>

O apoio da família é fundamental! Algumas dicas:
• As orientações médicas devem ser direcionadas pelos profissionais
• A decisão final é sempre da pessoa interessada
• Seu papel é oferecer apoio emocional e prático
• Acompanhe as consultas quando possível

Estou aqui para tirar suas dúvidas sobre todo o processo! 💙"""
    
    set_user_state(message.from_user.id, UserState.HELPER_COMPLETED)
    markup = create_main_menu()
    bot.reply_to(message, response, reply_markup=markup)

def handle_age_input(message, user_data):
    try:
        age = int(message.text.strip())
        if age < 16:
            bot.reply_to(message, "⚠️ A cirurgia bariátrica é indicada para pessoas a partir de 16 anos. Para menores, é necessário avaliação médica especializada.")
            return
        elif age > 65:
            age_warning = f"⚠️ <b>Atenção, {user_data.name}!</b>\n\nA cirurgia bariátrica após os 65 anos requer avaliação médica muito criteriosa. Recomendo consultar um cirurgião especialista para análise individual."
            bot.reply_to(message, age_warning)
        
        user_data.age = str(age)
        set_user_state(message.from_user.id, UserState.WAITING_GENDER)
        
        gender_msg = f"4️⃣ Qual é o seu gênero, {user_data.name}?"
        markup = create_gender_keyboard()
        bot.reply_to(message, gender_msg, reply_markup=markup)
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para a idade (exemplo: 35)")

def handle_gender_input_text(message, user_data):
    """Fallback para entrada de gênero por texto"""
    gender = message.text.strip().lower()
    
    if gender in ['masculino', 'homem', 'm']:
        user_data.gender = 'masculino'
        response_msg = f"Obrigado, {user_data.name}! 😊"
    elif gender in ['feminino', 'mulher', 'f']:
        user_data.gender = 'feminino'
        response_msg = f"Obrigada, {user_data.name}! 😊"
    elif gender in ['outro', 'outros', 'não-binário', 'nao-binario', 'nb']:
        user_data.gender = 'outro'
        response_msg = f"Obrigada, {user_data.name}! 😊"
    else:
        markup = create_gender_keyboard()
        bot.reply_to(message, "Pode escolher uma das opções abaixo?", reply_markup=markup)
        return
    
    set_user_state(message.from_user.id, UserState.WAITING_HEIGHT)
    bot.reply_to(message, f"{response_msg}\n\n5️⃣ Qual é a sua altura? (exemplo: 170 cm)")

def handle_height_input(message, user_data):
    try:
        height_text = message.text.strip().replace(',', '.').replace('cm', '').replace('m', '')
        height = float(height_text)
        
        if height < 100 or height > 250:
            bot.reply_to(message, "⚠️ Altura inválida. Digite a altura em centímetros (exemplo: 170)")
            return
        
        user_data.height = str(int(height))
        set_user_state(message.from_user.id, UserState.WAITING_WEIGHT)
        bot.reply_to(message, f"6️⃣ E qual é o seu peso atual? (exemplo: 85 kg)")
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para a altura (exemplo: 170)")

def handle_weight_input(message, user_data):
    try:
        weight_text = message.text.strip().replace(',', '.').replace('kg', '')
        weight = float(weight_text)
        
        if weight < 30 or weight > 300:
            bot.reply_to(message, "⚠️ Peso inválido. Digite o peso em quilogramas (exemplo: 85)")
            return
        
        user_data.weight = str(weight)
        
        # Calcular IMC e gerar resposta personalizada
        imc = calculate_imc(user_data.weight, user_data.height)
        classification, emoji = get_imc_classification(imc)
        
        response = f"""✅ <b>Perfil completo, {user_data.name}!</b>

📊 <b>Seus dados:</b>
• Idade: {user_data.age} anos
• Altura: {user_data.height} cm
• Peso: {user_data.weight} kg
• IMC: {imc} kg/m² {emoji}
• Classificação: {classification}

"""
        
        # Orientação baseada no IMC
        if imc >= 40:
            response += """🎯 <b>Orientação:</b>
Você atende ao critério de IMC ≥ 40 kg/m² para cirurgia bariátrica. Recomendo consultar um cirurgião especialista para avaliação completa!"""
        elif imc >= 35:
            response += """🎯 <b>Orientação:</b>
Você tem IMC ≥ 35 kg/m². Para cirurgia bariátrica, seria necessário também ter comorbidades (diabetes, hipertensão, apneia do sono, etc.). Consulte um médico especialista!"""
        elif imc >= 30:
            response += """🎯 <b>Orientação:</b>
Você está na faixa de obesidade grau I. A cirurgia bariátrica geralmente é indicada para IMC ≥ 35 kg/m² com comorbidades ou ≥ 40 kg/m². Consulte um endocrinologista primeiro!"""
        else:
            response += """🎯 <b>Orientação:</b>
Seu IMC não está na faixa para cirurgia bariátrica (≥ 35 kg/m² com comorbidades ou ≥ 40 kg/m²). Consulte um nutricionista ou endocrinologista para orientação adequada!"""
        
        set_user_state(message.from_user.id, UserState.COMPLETED)
        markup = create_main_menu()
        bot.reply_to(message, response, reply_markup=markup)
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para o peso (exemplo: 85)")

def handle_quick_imc_height(message, user_data):
    try:
        height_text = message.text.strip().replace(',', '.').replace('cm', '').replace('m', '')
        height = float(height_text)
        
        if height < 100 or height > 250:
            bot.reply_to(message, "⚠️ Altura inválida. Digite a altura em centímetros (exemplo: 170)")
            return
        
        user_data.height = str(int(height))
        set_user_state(message.from_user.id, UserState.QUICK_IMC_WEIGHT)
        bot.reply_to(message, "2️⃣ Agora digite seu peso em quilogramas (exemplo: 85):")
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para a altura (exemplo: 170)")

def handle_quick_imc_weight(message, user_data):
    try:
        weight_text = message.text.strip().replace(',', '.').replace('kg', '')
        weight = float(weight_text)
        
        if weight < 30 or weight > 300:
            bot.reply_to(message, "⚠️ Peso inválido. Digite o peso em quilogramas (exemplo: 85)")
            return
        
        # Calcular IMC
        imc = calculate_imc(str(weight), user_data.height)
        classification, emoji = get_imc_classification(imc)
        
        response = f"""🧮 <b>Resultado do IMC:</b>

📊 <b>Dados:</b>
• Altura: {user_data.height} cm
• Peso: {weight} kg
• IMC: {imc} kg/m² {emoji}
• Classificação: {classification}

"""
        
        # Orientação baseada no IMC
        if imc >= 40:
            response += """🎯 <b>Orientação:</b>
IMC ≥ 40 kg/m² atende ao critério para cirurgia bariátrica. Consulte um cirurgião especialista!"""
        elif imc >= 35:
            response += """🎯 <b>Orientação:</b>
IMC ≥ 35 kg/m². Para cirurgia bariátrica, seria necessário ter também comorbidades. Consulte um médico especialista!"""
        elif imc >= 30:
            response += """🎯 <b>Orientação:</b>
Obesidade grau I. Cirurgia bariátrica geralmente indicada para IMC ≥ 35 com comorbidades ou ≥ 40. Consulte um endocrinologista!"""
        else:
            response += """🎯 <b>Orientação:</b>
IMC não está na faixa para cirurgia bariátrica. Consulte um nutricionista ou endocrinologista para orientação adequada!"""
        
        set_user_state(message.from_user.id, UserState.GENERAL_CHAT)
        markup = create_main_menu()
        bot.reply_to(message, response, reply_markup=markup)
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para o peso (exemplo: 85)")

def handle_general_question(message, user_data):
    """Handler para perguntas gerais usando IA"""
    try:
        # Verificar novamente se é pergunta restrita
        if is_restricted_question(message.text):
            markup = create_main_menu()
            bot.reply_to(message, get_restriction_message(), reply_markup=markup)
            return
        
        # Mostrar que está processando
        processing_msg = bot.reply_to(message, "🤔 Pensando...")
        
        # Obter resposta da IA
        ai_response = ask_grok(message.text, user_data)
        
        # Editar mensagem com resposta
        markup = create_main_menu()
        bot.edit_message_text(
            f"{ai_response}\n\n💙 <i>Outras dúvidas?</i>",
            processing_msg.chat.id,
            processing_msg.message_id,
            reply_markup=markup
        )
    
    except Exception as e:
        logger.error(f"Error in general question handler: {e}")
        markup = create_main_menu()
        bot.reply_to(message, "Ops! Tive um probleminha. Pode tentar novamente?", reply_markup=markup)

# Função de limpeza periódica
def periodic_cleanup():
    """Executa limpeza periódica das sessões"""
    while True:
        try:
            time.sleep(3600)  # 1 hora
            cleanup_old_sessions()
            logger.info("Periodic cleanup completed")
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}")

# Configuração do webhook
def setup_webhook():
    try:
        if ENVIRONMENT == 'production' and WEBHOOK_URL:
            webhook_url = f"{WEBHOOK_URL}/webhook"
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook configurado: {webhook_url}")
        else:
            bot.remove_webhook()
            logger.info("Webhook removido - modo desenvolvimento")
    except Exception as e:
        logger.error(f"Erro ao configurar webhook: {e}")

# Função principal
def main():
    try:
        logger.info("Iniciando BarIA Bot v3.0...")
        logger.info(f"Environment: {ENVIRONMENT}")
        
        # Configurar webhook se em produção
        if ENVIRONMENT == 'production':
            setup_webhook()
            
            # Iniciar thread de limpeza
            cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
            cleanup_thread.start()
            
            # Iniciar Flask
            port = int(os.environ.get('PORT', 5000))
            app.run(host='0.0.0.0', port=port)
        else:
            # Modo desenvolvimento - polling
            logger.info("Iniciando modo polling...")
            bot.remove_webhook()
            
            # Thread de limpeza
            cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
            cleanup_thread.start()
            
            # Polling
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
    
    except Exception as e:
        logger.error(f"Erro crítico: {e}")
        raise

if __name__ == '__main__':
    main()
