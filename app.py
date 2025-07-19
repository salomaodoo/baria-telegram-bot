#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BarIA Bot v3.0 - Bot para cálculo de IMC e orientações sobre cirurgia bariátrica
"""

import os
import time
import threading
import logging
from flask import Flask, request
import telebot
from telebot import types

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações do bot
BOT_TOKEN = os.environ.get('BOT_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN não encontrado nas variáveis de ambiente")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Estados do usuário
class UserState:
    GENERAL_CHAT = "general_chat"
    WAITING_NAME = "waiting_name"
    WAITING_AGE = "waiting_age"
    WAITING_HEIGHT = "waiting_height"
    WAITING_WEIGHT = "waiting_weight"
    QUICK_IMC_HEIGHT = "quick_imc_height"
    QUICK_IMC_WEIGHT = "quick_imc_weight"
    COMPLETED = "completed"

# Dados do usuário
class UserData:
    def __init__(self):
        self.name = ""
        self.age = ""
        self.height = ""
        self.weight = ""
        self.state = UserState.GENERAL_CHAT

# Armazenamento em memória
user_sessions = {}
user_states = {}

def get_user_data(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = UserData()
    return user_sessions[user_id]

def set_user_state(user_id, state):
    user_states[user_id] = state
    user_sessions[user_id].state = state

def get_user_state(user_id):
    return user_states.get(user_id, UserState.GENERAL_CHAT)

def cleanup_old_sessions():
    """Remove sessões antigas"""
    # Implementar lógica de limpeza se necessário
    pass

def calculate_imc(weight, height):
    """Calcula o IMC"""
    try:
        weight_kg = float(weight)
        height_m = float(height) / 100  # converter cm para metros
        imc = weight_kg / (height_m ** 2)
        return round(imc, 1)
    except (ValueError, ZeroDivisionError):
        return 0

def get_imc_classification(imc):
    """Retorna classificação do IMC e emoji"""
    if imc < 18.5:
        return "Abaixo do peso", "⬇️"
    elif imc < 25:
        return "Peso normal", "✅"
    elif imc < 30:
        return "Sobrepeso", "⚠️"
    elif imc < 35:
        return "Obesidade grau I", "🔴"
    elif imc < 40:
        return "Obesidade grau II", "🔴🔴"
    else:
        return "Obesidade grau III", "🔴🔴🔴"

def create_main_menu():
    """Cria menu principal"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("📝 Cadastro Completo")
    btn2 = types.KeyboardButton("🧮 Calcular IMC")
    btn3 = types.KeyboardButton("❓ Fazer Pergunta")
    btn4 = types.KeyboardButton("📊 Meus Dados")
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    return markup

def is_restricted_question(text):
    """Verifica se é uma pergunta restrita"""
    restricted_keywords = [
        "medicamento", "remédio", "dose", "posologia", "prescrição",
        "diagnóstico", "tratamento específico", "cirurgia urgente"
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in restricted_keywords)

def get_restriction_message():
    """Mensagem para perguntas restritas"""
    return """⚠️ Esta pergunta envolve orientação médica específica.

🏥 Para sua segurança, consulte sempre um profissional de saúde qualificado para:
• Prescrições de medicamentos
• Diagnósticos médicos  
• Tratamentos específicos

💙 Posso ajudar com informações gerais sobre cirurgia bariátrica!"""

def get_smart_response(question, user_data):
    """Gera resposta inteligente para perguntas gerais"""
    question_lower = question.lower()
    
    # Respostas sobre cirurgia bariátrica
    if any(word in question_lower for word in ["bariátrica", "bariatrica", "cirurgia", "operação"]):
        return """🏥 <b>Sobre Cirurgia Bariátrica:</b>

A cirurgia bariátrica é indicada para:
• IMC ≥ 40 kg/m²
• IMC ≥ 35 kg/m² com comorbidades

<b>Principais técnicas:</b>
• Bypass Gástrico
• Sleeve (Manga Gástrica)
• Banda Gástrica

<b>Benefícios:</b>
• Perda de peso significativa
• Melhora do diabetes
• Redução da pressão arterial
• Melhora da qualidade de vida

⚠️ <i>Sempre consulte um cirurgião especialista!</i>"""
    
    # Resposta padrão
    return """💙 Obrigado pela pergunta! 

Para informações específicas sobre cirurgia bariátrica, recomendo:

🏥 <b>Consultar especialistas:</b>
• Cirurgião bariátrico
• Endocrinologista
• Nutricionista

📱 <b>Use o bot para:</b>
• Calcular seu IMC
• Entender critérios básicos
• Informações gerais

<i>Sua saúde é importante - busque orientação médica profissional!</i>"""

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK"

# Handlers do bot
@bot.message_handler(commands=['start'])
def start_command(message):
    user_name = message.from_user.first_name or "amigo(a)"
    welcome_text = f"""🤖 <b>Olá, {user_name}! Bem-vindo ao BarIA Bot!</b>

💙 Sou seu assistente para informações sobre cirurgia bariátrica.

<b>O que posso fazer:</b>
• 📝 Cadastro completo com orientações
• 🧮 Cálculo rápido de IMC
• ❓ Responder dúvidas gerais
• 📊 Gerenciar seus dados

<b>Escolha uma opção abaixo:</b>"""
    
    markup = create_main_menu()
    bot.reply_to(message, welcome_text, reply_markup=markup, parse_mode='HTML')
    set_user_state(message.from_user.id, UserState.GENERAL_CHAT)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    current_state = get_user_state(user_id)
    
    # Comandos do menu
    if message.text == "📝 Cadastro Completo":
        set_user_state(user_id, UserState.WAITING_NAME)
        bot.reply_to(message, "1️⃣ Vamos começar! Qual é o seu nome?")
        return
    
    elif message.text == "🧮 Calcular IMC":
        set_user_state(user_id, UserState.QUICK_IMC_HEIGHT)
        bot.reply_to(message, "1️⃣ Digite sua altura em centímetros (exemplo: 170):")
        return
    
    elif message.text == "❓ Fazer Pergunta":
        set_user_state(user_id, UserState.GENERAL_CHAT)
        bot.reply_to(message, "💬 Faça sua pergunta sobre cirurgia bariátrica:")
        return
    
    elif message.text == "📊 Meus Dados":
        if user_data.name:
            response = f"""📊 <b>Seus dados salvos:</b>

• Nome: {user_data.name}
• Idade: {user_data.age} anos
• Altura: {user_data.height} cm
• Peso: {user_data.weight} kg"""
            
            if user_data.height and user_data.weight:
                imc = calculate_imc(user_data.weight, user_data.height)
                classification, emoji = get_imc_classification(imc)
                response += f"\n• IMC: {imc} kg/m² {emoji}\n• Classificação: {classification}"
        else:
            response = "📝 Você ainda não fez seu cadastro completo. Use '📝 Cadastro Completo' para começar!"
        
        markup = create_main_menu()
        bot.reply_to(message, response, reply_markup=markup, parse_mode='HTML')
        return
    
    # Estados específicos
    if current_state == UserState.WAITING_NAME:
        handle_name_input(message, user_data)
    elif current_state == UserState.WAITING_AGE:
        handle_age_input(message, user_data)
    elif current_state == UserState.WAITING_HEIGHT:
        handle_height_input(message, user_data)
    elif current_state == UserState.WAITING_WEIGHT:
        handle_weight_input(message, user_data)
    elif current_state == UserState.QUICK_IMC_HEIGHT:
        handle_quick_imc_height(message, user_data)
    elif current_state == UserState.QUICK_IMC_WEIGHT:
        handle_quick_imc_weight(message, user_data)
    else:
        handle_general_question(message, user_data)

def handle_name_input(message, user_data):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        bot.reply_to(message, "⚠️ Nome deve ter entre 2 e 50 caracteres. Tente novamente:")
        return
    
    user_data.name = name
    set_user_state(message.from_user.id, UserState.WAITING_AGE)
    bot.reply_to(message, f"2️⃣ Prazer, {name}! Qual é a sua idade?")

def handle_age_input(message, user_data):
    try:
        age = int(message.text.strip())
        if age < 16 or age > 100:
            bot.reply_to(message, "⚠️ Idade inválida. Digite sua idade (16-100 anos):")
            return
        
        user_data.age = str(age)
        set_user_state(message.from_user.id, UserState.WAITING_HEIGHT)
        bot.reply_to(message, "3️⃣ Qual é a sua altura em centímetros? (exemplo: 170)")
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para a idade:")

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
        bot.reply_to(message, response, reply_markup=markup, parse_mode='HTML')
    
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
        bot.reply_to(message, response, reply_markup=markup, parse_mode='HTML')
    
    except ValueError:
        bot.reply_to(message, "Por favor, digite apenas números para o peso (exemplo: 85)")

def handle_general_question(message, user_data):
    """Handler para perguntas gerais usando sistema inteligente"""
    try:
        # Verificar novamente se é pergunta restrita
        if is_restricted_question(message.text):
            markup = create_main_menu()
            bot.reply_to(message, get_restriction_message(), reply_markup=markup, parse_mode='HTML')
            return
        
        # Obter resposta inteligente
        smart_response = get_smart_response(message.text, user_data)
        
        # Enviar resposta
        markup = create_main_menu()
        bot.reply_to(message, f"{smart_response}\n\n💙 <i>Outras dúvidas?</i>", reply_markup=markup, parse_mode='HTML')
    
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
