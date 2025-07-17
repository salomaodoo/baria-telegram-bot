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

def get_ans_criteria_message(imc):
    """Retorna mensagem sobre critérios da ANS"""
    if imc >= 40:
        return """✅ **Pelo seu IMC, você atende aos critérios da ANS para cirurgia bariátrica:**
• IMC ≥ 40 kg/m²"""
    elif imc >= 35:
        return """⚠️ **Você pode atender aos critérios da ANS se tiver comorbidades:**
• IMC entre 35-39,9 kg/m²
• É necessário ter comorbidades como diabetes, hipertensão, apneia do sono, etc.
• Será preciso avaliação médica para confirmar"""
    else:
        return """❌ **Pelo IMC atual, você não atende aos critérios básicos da ANS:**
• IMC < 35 kg/m²
• Converse com um médico sobre outras opções"""

def get_pathways_message():
    """Retorna informações sobre caminhos - SEM VALORES"""
    return """🏥 **Caminhos para cirurgia bariátrica:**

🔹 **Particular:**
• Consulte diretamente com cirurgiões especializados
• Para informações sobre custos, consulte profissionais habilitados

🔹 **Plano de Saúde:**
• Cobertura obrigatória pela ANS
• Período de carência: 24 meses
• Consulte seu plano para prazos específicos

🔹 **SUS:**
• Totalmente gratuito
• Consulte unidades de saúde para informações sobre fila de espera

📋 **Documentos necessários:**
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
    return """⚠️ **Informação restrita**

Para informações sobre valores, tempos de cirurgia e métodos cirúrgicos específicos, você deve consultar diretamente com:

• Cirurgiões especializados
• Hospitais credenciados
• Seu plano de saúde
• Unidades do SUS

Posso ajudar com outras dúvidas sobre critérios da ANS e documentação necessária! 💙"""

def get_gender_neutral_message(name):
    """Retorna mensagem sem gênero específico"""
    return f"Obrigada, {name}! 😊"

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

# Handlers
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data.state = UserState.INITIAL
    
    cleanup_old_sessions()
    
    response = """Olá! 👋 Eu sou a BarIA, sua assistente virtual focada em cirurgia bariátrica no Brasil. Posso te fazer algumas perguntinhas para entender melhor sua situação e te ajudar nessa jornada?"""
    
    set_user_state(user_id, UserState.WAITING_CONSENT)
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['criterios', 'documentos', 'caminhos', 'orientacoes'])
def handle_custom_commands(message):
    command = message.text.lower().strip()
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    
    if command == '/criterios':
        response = """📋 **Critérios da ANS para cirurgia bariátrica:**

✅ **Critérios obrigatórios:**
• IMC ≥ 40 kg/m² OU
• IMC ≥ 35 kg/m² + comorbidades (diabetes, hipertensão, apneia do sono, etc.)
• Idade entre 16 e 65 anos
• Tentativas de tratamento clínico sem sucesso por pelo menos 2 anos

⚠️ **Observações importantes:**
• Avaliação médica multidisciplinar obrigatória
• Acompanhamento psicológico necessário
• Carência de 24 meses no plano de saúde

Para avaliação individual, consulte um cirurgião especialista! 💙"""
    
    elif command == '/documentos':
        response = """📄 **Documentos necessários:**

🔹 **Documentos pessoais:**
• RG e CPF
• Comprovante de residência atualizado
• Cartão do SUS ou carteira do plano de saúde

🔹 **Documentos médicos:**
• Histórico médico completo
• Exames anteriores (se houver)
• Relatórios de tentativas de tratamento clínico
• Comprovação de comorbidades (se aplicável)

🔹 **Para planos de saúde:**
• Declaração de carência cumprida
• Guia de solicitação de procedimento

Consulte sempre com o local onde fará o procedimento para lista completa! 💙"""
    
    elif command == '/caminhos':
        response = get_pathways_message()
    
    elif command == '/orientacoes':
        response = """💡 **Orientações gerais:**

🔹 **Antes da cirurgia:**
• Consulte cirurgião especialista
• Faça avaliação multidisciplinar
• Prepare-se psicologicamente
• Organize documentação

🔹 **Pós-operatório:**
• Siga rigorosamente as orientações médicas
• Mantenha acompanhamento nutricional
• Realize atividade física conforme orientação
• Participe de grupos de apoio

🔹 **Dicas importantes:**
• Não tome decisões por impulso
• Busque informações em fontes confiáveis
• Conte com apoio familiar
• Tenha paciência com o processo

Outras dúvidas específicas? 💙"""
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['reset'])
def handle_reset(message):
    user_id = message.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    bot.send_message(message.chat.id, "✅ Dados resetados! Digite /start para começar novamente.")

# Handler principal de mensagens
@bot.message_handler(func=lambda message: True)
def handle_text_message(message):
    try:
        user_id = message.from_user.id
        user_data = get_user_data(user_id)
        text = message.text.strip()
        
        logger.info(f"User {user_id} ({user_data.state}): {text}")
        
        # Verificar se é uma pergunta restrita
        if is_restricted_question(text):
            bot.reply_to(message, get_restriction_message())
            return
        
        # Saudações iniciais
        if text.lower() in ['olá', 'oi', 'hello', 'hey', 'bom dia', 'boa tarde', 'boa noite']:
            if user_data.state == UserState.INITIAL:
                handle_start(message)
                return
        
        # Fluxo sequencial obrigatório
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
            handle_gender_input(message, user_data)
        elif user_data.state == UserState.WAITING_HEIGHT:
            handle_height_input(message, user_data)
        elif user_data.state == UserState.WAITING_WEIGHT:
            handle_weight_input(message, user_data)
        elif user_data.state in [UserState.COMPLETED, UserState.HELPER_COMPLETED, UserState.GENERAL_CHAT]:
            handle_general_question(message, user_data)
        else:
            bot.reply_to(message, "❌ Algo deu errado. Digite /start para começar novamente.")
    
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        bot.reply_to(message, "❌ Ocorreu um erro. Tente novamente ou digite /start.")

def handle_consent(message, user_data):
    text = message.text.lower().strip()
    
    if any(word in text for word in ['sim', 'claro', 'ok', 'pode', 'vamos', 'aceito']):
        set_user_state(message.from_user.id, UserState.WAITING_NAME)
        bot.reply_to(message, "1️⃣ Qual é o seu primeiro nome?")
    elif any(word in text for word in ['não', 'nao', 'agora não', 'depois']):
        set_user_state(message.from_user.id, UserState.GENERAL_CHAT)
        bot.reply_to(message, "Sem problemas! Posso te ajudar com dúvidas sobre cirurgia bariátrica. É só me perguntar! 💙")
    else:
        bot.reply_to(message, "Por favor, responda com 'sim' ou 'não'. Posso te fazer algumas perguntas para te ajudar melhor?")

def handle_name_input(message, user_data):
    name = message.text.strip()
    
    if len(name) < 2 or len(name) > 50:
        bot.reply_to(message, "Por favor, digite um nome válido.")
        return
    
    name = re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', name).title()
    user_data.name = name
    set_user_state(message.from_user.id, UserState.WAITING_PATIENT_CONFIRMATION)
    
    bot.reply_to(message, f"Obrigada, {user_data.name}! 😊\n\n2️⃣ Você é a pessoa interessada na cirurgia bariátrica?")

def handle_patient_confirmation(message, user_data):
    text = message.text.lower().strip()
    
    if any(word in text for word in ['sim', 'sou', 'eu', 'própria', 'mesmo']):
        user_data.is_patient = True
        set_user_state(message.from_user.id, UserState.WAITING_AGE)
        bot.reply_to(message, f"Perfeito, {user_data.name}!\n\n3️⃣ Qual é a sua idade?")
    
    elif any(word in text for word in ['não', 'nao', 'outra', 'alguém']):
        user_data.is_patient = False
        set_user_state(message.from_user.id, UserState.WAITING_RELATIONSHIP)
        bot.reply_to(message, f"Entendi, {user_data.name}. É muito importante o apoio da família!\n\n3️⃣ Qual é o seu grau de parentesco com a pessoa interessada?")
    
    else:
        bot.reply_to(message, "Por favor, responda 'sim' se você é a pessoa interessada na cirurgia, ou 'não' se está buscando informações para auxiliar outra pessoa.")

def handle_relationship_input(message, user_data):
    user_data.relationship = message.text.strip()
    
    message_text = f"""Obrigada, {user_data.name}!

💙 **Orientações sobre apoio familiar:**

• As orientações médicas devem sempre ser direcionadas pelos profissionais habilitados
• A decisão final é sempre da pessoa interessada
• Não é ético forçar ou indicar de forma incisiva procedimentos cirúrgicos a outra pessoa
• Seu papel é oferecer apoio emocional

**Documentos que podem ser necessários:**
• RG e CPF
• Cartão do SUS ou plano de saúde
• Comprovante de residência

Posso continuar te ajudando com dúvidas sobre o processo. É só me perguntar! 💙"""
    
    set_user_state(message.from_user.id, UserState.HELPER_COMPLETED)
    bot.reply_to(message, message_text)

def handle_age_input(message, user_data):
    try:
        age = int(message.text.strip())
        if age < 16:
            bot.reply_to(message, "A cirurgia bariátrica é recomendada apenas para pessoas com 16 anos ou mais.")
            return
        elif age > 100:
            bot.reply_to(message, "Por favor, digite uma idade válida.")
            return
        
        user_data.age = str(age)
        set_user_state(message.from_user.id, UserState.WAITING_GENDER)
        
        response_msg = get_gendered_message(user_data.name, user_data.gender) if user_data.gender else f"Obrigada, {user_data.name}! 😊"
        bot.reply_to(message, f"{response_msg}\n\n4️⃣ Qual é o seu gênero?\n\n• Masculino\n• Feminino\n• Outro")
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para a idade.")

def handle_gender_input(message, user_data):
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
        bot.reply_to(message, "Por favor, escolha: masculino, feminino ou outro.")
        return
    
    set_user_state(message.from_user.id, UserState.WAITING_HEIGHT)
    bot.reply_to(message, f"{response_msg}\n\n5️⃣ Qual é a sua altura?\n\nDigite em centímetros (exemplo: 170)")

def handle_height_input(message, user_data):
    try:
        height_text = message.text.strip().replace(',', '.')
        height = float(height_text)
        
        if height < 100 or height > 250:
            bot.reply_to(message, "Por favor, digite uma altura válida em centímetros.")
            return
        
        user_data.height = str(height)
        set_user_state(message.from_user.id, UserState.WAITING_WEIGHT)
        
        response_msg = get_gendered_message(user_data.name, user_data.gender)
        bot.reply_to(message, f"{response_msg}\n\n6️⃣ Qual é o seu peso atual?\n\nDigite em quilos (exemplo: 85)")
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para a altura.")

def handle_weight_input(message, user_data):
    try:
        weight_text = message.text.strip().replace(',', '.')
        weight = float(weight_text)
        
        if weight < 30 or weight > 300:
            bot.reply_to(message, "Por favor, digite um peso válido em quilos.")
            return
        
        user_data.weight = str(weight)
        set_user_state(message.from_user.id, UserState.COMPLETED)
        
        # Calcular IMC e enviar relatório completo
        send_complete_report(message, user_data)
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para o peso.")

def send_complete_report(message, user_data):
    imc = calculate_imc(user_data.weight, user_data.height)
    
    if imc is None:
        bot.reply_to(message, "❌ Erro ao calcular IMC. Verifique os dados.")
        return
    
    classification, icon = get_imc_classification(imc)
    ans_criteria = get_ans_criteria_message(imc)
    pathways = get_pathways_message()
    
    response_msg = get_gendered_message(user_data.name, user_data.gender)
    
    report = f"""{response_msg}

📊 **Seus dados:**
• Nome: {user_data.name}
• Idade: {user_data.age} anos
• Altura: {user_data.height} cm
• Peso: {user_data.weight} kg

🔢 **IMC:** {imc} kg/m²
{icon} **Classificação:** {classification}

{ans_criteria}

{pathways}

Posso continuar te ajudando com dicas e orientações sobre o pré e pós cirúrgico da bariátrica. É só me chamar! 💙"""
    
    bot.reply_to(message, report)

def handle_general_question(message, user_data):
    """Respostas para perguntas gerais"""
    text = message.text.strip()
    
    # Verificar se é uma pergunta restrita
    if is_restricted_question(text):
        bot.reply_to(message, get_restriction_message())
        return
    
    text_lower = text.lower()
    
    # Critérios da ANS
    if any(word in text_lower for word in ['criterios', 'critérios', 'ans', 'requisitos', 'exigências', 'condições']):
        response = """📋 **Critérios da ANS para cirurgia bariátrica:**

✅ **Critérios obrigatórios:**
• IMC ≥ 40 kg/m² OU
• IMC ≥ 35 kg/m² + comorbidades (diabetes, hipertensão, apneia do sono, etc.)
• Idade entre 16 e 65 anos
• Tentativas de tratamento clínico sem sucesso por pelo menos 2 anos

⚠️ **Observações importantes:**
• Avaliação médica multidisciplinar obrigatória
• Acompanhamento psicológico necessário
• Carência de 24 meses no plano de saúde

Para avaliação individual, consulte um cirurgião especialista! 💙"""
    
    # Documentos necessários
    elif any(word in text_lower for word in ['documentos', 'papéis', 'papeis', 'documentação', 'preciso levar']):
        response = """📄 **Documentos necessários:**

🔹 **Documentos pessoais:**
• RG e CPF
• Comprovante de residência atualizado
• Cartão do SUS ou carteira do plano de saúde

🔹 **Documentos médicos:**
• Histórico médico completo
• Exames anteriores (se houver)
• Relatórios de tentativas de tratamento clínico
• Comprovação de comorbidades (se aplicável)

🔹 **Para planos de saúde:**
• Declaração de carência cumprida
• Guia de solicitação de procedimento

Consulte sempre com o local onde fará o procedimento para lista completa! 💙"""
    
    # Caminhos para cirurgia
    elif any(word in text_lower for word in ['caminhos', 'caminho', 'onde fazer', 'como fazer', 'particular', 'plano', 'sus']):
        response = get_pathways_message()
    
    # Orientações gerais
    elif any(word in text_lower for word in ['orientações', 'orientacoes', 'gerais', 'geral', 'informações', 'informacoes']):
        response = """💡 **Orientações gerais:**

🔹 **Antes da cirurgia:**
• Consulte cirurgião especialista
• Faça avaliação multidisciplinar
• Prepare-se psicologicamente
• Organize documentação

🔹 **Pós-operatório:**
• Siga rigorosamente as orientações médicas
• Mantenha acompanhamento nutricional
• Realize atividade física conforme orientação
• Participe de grupos de apoio

🔹 **Dicas importantes:**
• Não tome decisões por impulso
• Busque informações em fontes confiáveis
• Conte com apoio familiar
• Tenha paciência com o processo

Outras dúvidas específicas? 💙"""
    
    # Dieta e alimentação
    elif any(word in text_lower for word in ['dieta', 'alimentação', 'comer', 'comida', 'nutrição']):
        response = """🥗 **Sobre alimentação:**

Para orientações sobre alimentação pré e pós-operatória, é fundamental consultar um nutricionista ou nutrólogo habilitado. Eles são os profissionais capacitados para criar planos alimentares adequados às suas necessidades específicas.

Cada caso é único e requer acompanhamento profissional personalizado.

Posso te ajudar com outras dúvidas sobre cirurgia bariátrica! 💙"""
    
    # Técnicas cirúrgicas
    elif any(word in text_lower for word in ['técnica', 'tecnica', 'bypass', 'sleeve', 'banda', 'cirurgia', 'tipos']):
        response = """🔬 **Principais técnicas:**

• **Sleeve:** Reduz o tamanho do estômago
• **Bypass:** Altera o trajeto dos alimentos
• **Banda:** Utiliza um anel no estômago

A escolha da técnica deve ser discutida com o cirurgião especialista, pois depende de vários fatores individuais como IMC, comorbidades, histórico médico e preferências.

Para detalhes técnicos específicos, consulte profissionais habilitados.

Outras dúvidas? 💙"""
    
    # Recuperação
    elif any(word in text_lower for word in ['recuperação', 'recuperacao', 'pós-operatório', 'pos-operatorio', 'depois']):
        response = """🏥 **Recuperação:**

• Acompanhamento médico regular é fundamental
• Retorno gradual às atividades normais
• Seguimento das orientações médicas
• Apoio nutricional e psicológico contínuo

Para informações específicas sobre tempos e detalhes do pós-operatório, consulte seu médico especialista.

Posso ajudar com mais alguma coisa? 💙"""
    
    # Resposta padrão
    else:
        response = f"""Olá{f', {user_data.name}' if user_data.name else ''}! 💙

Estou aqui para ajudar com dúvidas sobre cirurgia bariátrica. Posso falar sobre:

• **Critérios da ANS** - requisitos obrigatórios
• **Documentos necessários** - papéis para levar
• **Caminhos** - particular, plano de saúde, SUS
• **Orientações gerais** - dicas importantes

Digite uma dessas opções ou me faça uma pergunta específica!"""
    
    bot.reply_to(message, response)

# Handlers de erro
@bot.message_handler(func=lambda message: True, content_types=['photo', 'video', 'document', 'audio', 'voice'])
def handle_media(message):
    bot.reply_to(message, "Trabalho apenas com mensagens de texto. Como posso te ajudar? 💙")

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
        bot.remove_webhook()
        bot.infinity_polling()

# Inicialização
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    
    if ENVIRONMENT == 'production':
        setup_webhook()
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()
        app.run(host='0.0.0.0', port=port, debug=True)
