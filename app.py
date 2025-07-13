import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
from flask import Flask

# Configuração do bot - USANDO VARIÁVEL DE AMBIENTE
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN não encontrado nas variáveis de ambiente")

bot = telebot.TeleBot(BOT_TOKEN)

# Configuração do Flask para manter o serviço ativo
app = Flask(__name__)

@app.route('/')
def home():
    return {
        "status": "BarIA Bot está rodando!",
        "bot_info": "Assistente virtual para cirurgia bariátrica",
        "timestamp": "online"
    }

@app.route('/webhook', methods=['POST'])
def webhook():
    # Endpoint para webhook (se necessário)
    return "OK"

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

def get_user_data(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = UserData()
    return user_sessions[user_id]

def set_user_state(user_id, state):
    user_data = get_user_data(user_id)
    user_data.state = state

def calculate_imc(weight, height):
    """Calcula o IMC"""
    try:
        weight_kg = float(weight)
        height_m = float(height) / 100  # converte cm para metros
        imc = weight_kg / (height_m ** 2)
        return round(imc, 2)
    except:
        return None

def get_imc_classification(imc):
    """Classifica o IMC"""
    if imc < 18.5:
        return "Baixo peso"
    elif imc < 25:
        return "Peso normal"
    elif imc < 30:
        return "Sobrepeso"
    elif imc < 35:
        return "Obesidade grau I"
    elif imc < 40:
        return "Obesidade grau II"
    else:
        return "Obesidade grau III (obesidade mórbida)"

def get_ans_criteria_message(imc):
    """Retorna mensagem sobre critérios da ANS"""
    if imc >= 40:
        return "✅ Você atende aos critérios da ANS para cirurgia bariátrica (IMC ≥ 40)."
    elif imc >= 35:
        return "⚠️ Você pode atender aos critérios da ANS se tiver comorbidades associadas (diabetes, hipertensão, apneia do sono, etc.)."
    else:
        return "❌ Pelo IMC atual, você não atende aos critérios básicos da ANS para cirurgia bariátrica."

def get_pathways_message():
    """Retorna mensagem sobre caminhos para cirurgia"""
    return """
🏥 **Caminhos para cirurgia bariátrica:**

**🔹 Particular:**
- Mais rápido
- Escolha livre do cirurgião
- Custo: R$ 15.000 a R$ 50.000

**🔹 Plano de Saúde:**
- Cobertura obrigatória pela ANS
- Período de carência: 24 meses
- Necessária avaliação multidisciplinar

**🔹 SUS:**
- Gratuito
- Fila de espera mais longa
- Disponível em centros especializados
"""

# Handlers de comandos
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    user_data.state = UserState.INITIAL
    
    response = """Olá! 👋 Eu sou a BarIA, sua assistente virtual focada em cirurgia bariátrica no Brasil. Posso te fazer algumas perguntinhas para entender melhor sua situação e te ajudar nessa jornada?"""
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Sim, vamos começar! 😊", callback_data="start_questions"))
    keyboard.add(InlineKeyboardButton("Só quero conversar", callback_data="general_chat"))
    
    bot.send_message(message.chat.id, response, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "start_questions")
def start_questions(call):
    user_id = call.from_user.id
    set_user_state(user_id, UserState.WAITING_NAME)
    
    bot.edit_message_text(
        "1️⃣ Qual é o seu primeiro nome?",
        call.message.chat.id,
        call.message.message_id
    )

@bot.callback_query_handler(func=lambda call: call.data == "general_chat")
def general_chat(call):
    user_id = call.from_user.id
    set_user_state(user_id, UserState.GENERAL_CHAT)
    
    bot.edit_message_text(
        "Perfeito! Estou aqui para te ajudar com dúvidas sobre cirurgia bariátrica. Pode me perguntar qualquer coisa! 💙",
        call.message.chat.id,
        call.message.message_id
    )

# Handler para mensagens de texto
@bot.message_handler(func=lambda message: True)
def handle_text_message(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    text = message.text.strip()
    
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
        bot.reply_to(message, "Desculpe, não entendi. Digite /start para começar novamente.")

def handle_name_input(message, user_data):
    user_data.name = message.text.strip()
    set_user_state(message.from_user.id, UserState.WAITING_PATIENT_CONFIRMATION)
    
    bot.reply_to(message, f"Obrigada, {user_data.name}! 😊\n\n2️⃣ Você é a pessoa interessada na cirurgia bariátrica, ou está buscando informações para auxiliar outra pessoa?")

def handle_patient_confirmation(message, user_data):
    text = message.text.lower().strip()
    
    if any(word in text for word in ['sim', 'sou', 'eu', 'própria', 'mesmo', 'para mim']):
        user_data.is_patient = True
        set_user_state(message.from_user.id, UserState.WAITING_AGE)
        bot.reply_to(message, f"Perfeito, {user_data.name}! Vamos continuar.\n\n3️⃣ Qual é a sua idade?")
    
    elif any(word in text for word in ['não', 'outra', 'outra pessoa', 'alguém', 'familiar']):
        user_data.is_patient = False
        set_user_state(message.from_user.id, UserState.WAITING_RELATIONSHIP)
        bot.reply_to(message, f"Entendi, {user_data.name}. É muito importante o apoio da família nessa jornada!\n\n3️⃣ Qual é o seu grau de parentesco com a pessoa interessada?")
    
    else:
        bot.reply_to(message, "Por favor, me diga se você é a pessoa interessada na cirurgia ou se está buscando informações para auxiliar outra pessoa.")

def handle_relationship_input(message, user_data):
    user_data.relationship = message.text.strip()
    
    message_text = f"""Obrigada pela informação, {user_data.name}! 

💙 **Orientações importantes sobre apoio:**

• As orientações médicas devem sempre ser direcionadas pelos profissionais habilitados
• A decisão será sempre da pessoa interessada na cirurgia
• Não é ético nem humano forçar ou indicar de forma incisiva qualquer modificação corporal ou procedimentos cirúrgicos a outra pessoa
• Seu papel é oferecer apoio emocional e acompanhar nas consultas, se solicitado

**Informações gerais sobre documentos necessários:**
- RG e CPF
- Cartão do SUS ou plano de saúde
- Comprovante de residência
- Exames médicos (serão solicitados pelo cirurgião)

Posso continuar te ajudando com orientações gerais sobre o pré e pós cirúrgico. É só me chamar! 💙"""
    
    set_user_state(message.from_user.id, UserState.COMPLETED)
    bot.reply_to(message, message_text)

def handle_age_input(message, user_data):
    try:
        age = int(message.text.strip())
        if age < 16 or age > 100:
            bot.reply_to(message, "Por favor, digite uma idade válida.")
            return
        
        user_data.age = str(age)
        set_user_state(message.from_user.id, UserState.WAITING_GENDER)
        bot.reply_to(message, f"Obrigada, {user_data.name}! 😊\n\n4️⃣ Qual é o seu gênero? (masculino/feminino/outro)")
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para a idade.")

def handle_gender_input(message, user_data):
    gender = message.text.strip().lower()
    
    if gender in ['masculino', 'homem', 'macho', 'm']:
        user_data.gender = 'masculino'
    elif gender in ['feminino', 'mulher', 'femea', 'f']:
        user_data.gender = 'feminino'
    elif gender in ['outro', 'outros', 'não-binário', 'nao-binario', 'nb']:
        user_data.gender = 'outro'
    else:
        bot.reply_to(message, "Por favor, digite: masculino, feminino ou outro.")
        return
    
    set_user_state(message.from_user.id, UserState.WAITING_HEIGHT)
    bot.reply_to(message, f"Obrigada, {user_data.name}! 😊\n\n5️⃣ Qual é a sua altura? (em centímetros, ex: 170)")

def handle_height_input(message, user_data):
    try:
        height = float(message.text.strip())
        if height < 100 or height > 250:
            bot.reply_to(message, "Por favor, digite uma altura válida em centímetros (ex: 170).")
            return
        
        user_data.height = str(height)
        set_user_state(message.from_user.id, UserState.WAITING_WEIGHT)
        bot.reply_to(message, f"Obrigada, {user_data.name}! 😊\n\n6️⃣ Qual é o seu peso atual? (em quilos, ex: 85)")
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para a altura (ex: 170).")

def handle_weight_input(message, user_data):
    try:
        weight = float(message.text.strip())
        if weight < 30 or weight > 300:
            bot.reply_to(message, "Por favor, digite um peso válido em quilos.")
            return
        
        user_data.weight = str(weight)
        set_user_state(message.from_user.id, UserState.COMPLETED)
        
        # Calcular IMC e enviar relatório completo
        send_complete_report(message, user_data)
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para o peso (ex: 85).")

def send_complete_report(message, user_data):
    imc = calculate_imc(user_data.weight, user_data.height)
    classification = get_imc_classification(imc)
    ans_criteria = get_ans_criteria_message(imc)
    pathways = get_pathways_message()
    
    # Adaptação de linguagem baseada no gênero
    if user_data.gender == 'masculino':
        pronoun = "você"
        article = "o"
    elif user_data.gender == 'feminino':
        pronoun = "você"
        article = "a"
    else:  # outro
        pronoun = "você"
        article = ""
    
    report = f"""Perfeito, {user_data.name}! Aqui está {article} sua análise completa:

📊 **Seus dados:**
• Nome: {user_data.name}
• Idade: {user_data.age} anos
• Altura: {user_data.height} cm
• Peso: {user_data.weight} kg

🔢 **IMC:** {imc} ({classification})

{ans_criteria}

{pathways}

💡 **Próximos passos:**
1. Consulte um cirurgião bariátrico qualificado
2. Realize avaliação multidisciplinar
3. Faça exames pré-operatórios

Posso continuar te ajudando com dicas e orientações sobre o pré e pós cirúrgico da bariátrica. É só me chamar! 💙"""
    
    bot.reply_to(message, report)

def handle_general_question(message, user_data):
    """Lida com perguntas gerais sobre cirurgia bariátrica"""
    text = message.text.lower()
    
    # Aqui você pode adicionar respostas para perguntas frequentes
    if any(word in text for word in ['dieta', 'alimentação', 'comer', 'comida']):
        response = f"Oi, {user_data.name}! Para orientações sobre dieta, é essencial buscar um profissional de saúde habilitado, como Nutricionistas ou Nutrólogos. Eles poderão te ajudar de forma personalizada! 🥗"
    
    elif any(word in text for word in ['técnica', 'bypass', 'sleeve', 'banda']):
        response = f"Existem diferentes técnicas cirúrgicas, {user_data.name}. Cada uma tem suas indicações específicas. Recomendo que discuta as opções com o cirurgião escolhido, pois ele avaliará qual é a melhor para o seu caso! 👨‍⚕️"
    
    elif any(word in text for word in ['recuperação', 'pós-operatório', 'depois']):
        response = f"A recuperação é fundamental, {user_data.name}! Geralmente inclui repouso, acompanhamento nutricional e psicológico. O cirurgião te dará todas as orientações específicas para seu caso! 🏥"
    
    else:
        response = f"Oi, {user_data.name}! Estou aqui para ajudar com dúvidas sobre cirurgia bariátrica. Pode ser mais específica sobre o que gostaria de saber? 💙"
    
    bot.reply_to(message, response)

# Função para rodar o bot
def run_bot():
    print("🤖 BarIA iniciada! Bot rodando...")
    bot.infinity_polling()

# Inicialização
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    
    # Rodar Flask e bot em threads separadas
    import threading
    
    # Thread para o bot
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Rodar Flask (para Railway/Render)
    app.run(host='0.0.0.0', port=port, debug=False)
