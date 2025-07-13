import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import openai  # ou sua biblioteca de IA preferida

# Configuração de logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Token do bot (coloque seu token aqui)
BOT_TOKEN = "SEU_TOKEN_AQUI"

# Prompt do sistema para a BarIA
SYSTEM_PROMPT = """
Você é a BarIA, uma assistente virtual especializada e empática, que orienta pessoas sobre cirurgia bariátrica no Brasil. Sua função é guiar o usuário passo a passo, com linguagem simples, acolhedora e humana.

⚠️ Regras obrigatórias (siga exatamente):
1. Faça apenas UMA pergunta por vez.
2. Só prossiga depois que o usuário responder à pergunta anterior.
3. Nunca antecipe informações nem forneça conteúdos antes de coletar os dados.
4. NÃO diga várias perguntas de uma vez como "Qual seu nome, idade, gênero, altura e peso?". Isso está proibido.
5. NÃO calcule IMC nem explique critérios sem os dados completos do usuário.
6. NÃO use variáveis genéricas como [user_name] ou [imc] — aguarde os dados reais.
7. NÃO dê dicas de dieta ou crie dietas, siga sempre para a orientação de busca por um profissional de saúde habilitado para isso, como Nutricionistas ou Nutrólogos.
8. NÃO utilize palavras de duplo sentido ou de difícil compreensão, preze sempre pela clareza e menor quantidade de texto.
9. NÃO cite fontes de informações não científicas caso seja questionado.
10. NÃO recomende uma técnica cirúrgica caso questionado, limite-se apenas a falar a diferença e recomende que a técnica seja discutida com o Cirurgião escolhido.
11. Dê a opção da pessoa se identificar como alguém que deseja auxiliar outra pessoa no processo. Recomende que orientações de condutas médicas devem ser sempre direcionadas pelos profissionais habilitados. E lembre a pessoa de que a decisão será sempre do paciente e que não é ético e nem muito menos humano forçar ou indicar de forma incisiva qualquer modificação corporal ou procedimentos cirúrgicos a outra pessoa.
12. Antes de questionar informações como peso e etc, após confirmar o nome, pergunte se a pessoa é a interessada na cirurgia, ou se ela que pretende fazer, caso a resposta seja SIM, siga normalmente, caso seja NÃO, questione o grau de parentesco com a pessoa para quem o usuário está procurando e siga com orientações éticas, mas não dê detalhes como IMC e etc, apenas informações gerais sobre documentos e a questão do apoio.
13. NÃO calcule o IMC caso a pessoa não seja a interessada/paciente da cirurgia, apenas oriente que isso é algo pessoal, mas NÃO CALCULE, siga com orientações de apoio e etc.
14. Você é do gênero feminino, pelo seu nome ser "a BarIA", assim, SEMPRE que se referir a você é no feminino.
15. Se a resposta da pergunta "Qual o seu gênero?" for "outro" NÃO TRATE A PESSOA NO MASCULINO OU FEMININO, UTILIZE LINGUAGEM SEM GÊNERO.

🎯 Quando o usuário disser "Olá", "Oi" ou algo informal, apenas cumprimente e pergunte:
"Olá! 👋 Eu sou a BarIA, sua assistente virtual focada em cirurgia bariátrica no Brasil. Posso te fazer algumas perguntinhas para entender melhor sua situação e te ajudar nessa jornada?"

Se o usuário disser "sim", pergunte:
"1️⃣ Qual é o seu primeiro nome?"

Depois de cada resposta, diga algo como:
"Obrigada, {{nome}}! 😊 Vamos para a próxima: Qual é sua idade?"

Repita isso até coletar nome, idade, gênero, altura e peso.
*Somente após* esses dados, calcule o IMC e apresente os critérios da ANS e os caminhos (particular, plano de saúde ou SUS).

Finalize com:
"Posso continuar te ajudando com dicas e orientações sobre o pré e pós cirúrgico da bariátrica. É só me chamar! 💙"
"""

# Armazenamento temporário de conversas (use Redis ou DB em produção)
user_conversations = {}

# Função para gerar resposta da IA
async def generate_ai_response(user_message: str, user_id: int) -> str:
    """
    Gera resposta usando IA com o prompt da BarIA
    Substitua por sua implementação de IA preferida
    """
    try:
        # Recupera histórico da conversa
        conversation_history = user_conversations.get(user_id, [])
        
        # Exemplo com OpenAI (ajuste conforme sua IA)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *conversation_history,
            {"role": "user", "content": user_message}
        ]
        
        # Chama a IA (substitua pela sua implementação)
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content
        
        # Atualiza histórico
        conversation_history.append({"role": "user", "content": user_message})
        conversation_history.append({"role": "assistant", "content": ai_response})
        
        # Mantém apenas as últimas 10 mensagens
        if len(conversation_history) > 10:
            conversation_history = conversation_history[-10:]
        
        user_conversations[user_id] = conversation_history
        
        return ai_response
        
    except Exception as e:
        logger.error(f"Erro ao gerar resposta: {e}")
        return "Desculpe, ocorreu um erro. Tente novamente em alguns instantes."

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando inicial do bot"""
    welcome_message = """
Olá! 👋 Eu sou a BarIA, sua assistente virtual focada em cirurgia bariátrica no Brasil.

Estou aqui para te orientar com informações claras e acolhedoras sobre:
• Critérios da ANS
• Documentos necessários  
• Caminhos: particular, plano ou SUS
• Apoio no pré e pós-operatório

Posso te fazer algumas perguntinhas para entender melhor sua situação e te ajudar nessa jornada?

Digite "sim" para começar ou use os comandos disponíveis.
    """
    
    # Teclado com opções principais
    keyboard = [
        [InlineKeyboardButton("✅ Sim, vamos começar!", callback_data='start_questions')],
        [InlineKeyboardButton("ℹ️ Informações gerais", callback_data='info_geral')],
        [InlineKeyboardButton("📋 Critérios ANS", callback_data='criterios_ans')],
        [InlineKeyboardButton("📄 Documentos necessários", callback_data='documentos')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

# Comando /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra lista de comandos disponíveis"""
    help_text = """
🤖 **Comandos disponíveis:**

/start - Iniciar conversa com a BarIA
/help - Lista de comandos disponíveis
/info - Informações sobre cirurgia bariátrica
/criterios - Critérios da ANS para cirurgia
/documentos - Documentos necessários
/apoio - Como apoiar alguém no processo
/contato - Informações de contato
/reset - Reiniciar conversa

💬 **Ou simplesmente me mande uma mensagem e conversamos!**
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# Comando /reset
async def reset_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reinicia a conversa do usuário"""
    user_id = update.effective_user.id
    if user_id in user_conversations:
        del user_conversations[user_id]
    
    await update.message.reply_text(
        "Conversa reiniciada! 🔄\n\n"
        "Vamos começar novamente. Digite /start para iniciar."
    )

# Handler para botões inline
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa cliques nos botões inline"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == 'start_questions':
        response = await generate_ai_response("sim", user_id)
        await query.edit_message_text(response)
    
    elif query.data == 'info_geral':
        info_text = """
📋 **Informações sobre Cirurgia Bariátrica**

A cirurgia bariátrica é um procedimento que ajuda no tratamento da obesidade mórbida.

**Tipos principais:**
• Bypass Gástrico
• Sleeve (Manga Gástrica)
• Banda Gástrica

**Caminhos para realizar:**
• Particular
• Plano de saúde
• SUS

Para informações personalizadas, inicie uma conversa comigo! 😊
        """
        await query.edit_message_text(info_text, parse_mode='Markdown')
    
    # Adicione outros handlers conforme necessário

# Handler para mensagens de texto
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa mensagens de texto do usuário"""
    user_message = update.message.text
    user_id = update.effective_user.id
    
    # Envia indicador de digitação
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # Gera resposta da IA
    response = await generate_ai_response(user_message, user_id)
    
    # Envia resposta
    await update.message.reply_text(response)

# Função principal
def main() -> None:
    """Inicia o bot"""
    # Cria a aplicação
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Adiciona handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset_conversation))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Inicia o bot
    print("Bot iniciado! 🤖")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
