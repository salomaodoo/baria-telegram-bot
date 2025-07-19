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
    """Handler para perguntas gerais usando sistema inteligente"""
    try:
        # Verificar novamente se é pergunta restrita
        if is_restricted_question(message.text):
            markup = create_main_menu()
            bot.reply_to(message, get_restriction_message(), reply_markup=markup)
            return
        
        # Obter resposta inteligente
        smart_response = get_smart_response(message.text, user_data)
        
        # Enviar resposta
        markup = create_main_menu()
        bot.reply_to(message, f"{smart_response}\n\n💙 <i>Outras dúvidas?</i>", reply_markup=markup)
    
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
