# BarIA - Bot do Telegram para Cirurgia Bariátrica

🤖 **BarIA** é um assistente virtual inteligente focado em fornecer informações sobre cirurgia bariátrica no Brasil.

## 🚀 Funcionalidades

- **Avaliação personalizada**: Coleta dados como nome, idade, altura e peso
- **Cálculo de IMC**: Calcula automaticamente o Índice de Massa Corporal
- **Critérios da ANS**: Informa sobre os critérios da Agência Nacional de Saúde
- **Orientações**: Fornece informações sobre caminhos para cirurgia (SUS, planos de saúde, particular)
- **Chat interativo**: Responde perguntas sobre dieta, técnicas cirúrgicas e recuperação
- **Suporte familiar**: Orientações para familiares que apoiam o paciente

## 📋 Pré-requisitos

- Python 3.10+
- Token do bot do Telegram (obtido do [@BotFather](https://t.me/BotFather))
- Conta no Railway ou Render para deploy

## 🔧 Instalação Local

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/baria-telegram-bot.git
cd baria-telegram-bot
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite o arquivo .env com seu token
```

4. Execute o bot:
```bash
python bot.py
```

## 🌐 Deploy

### Railway (Recomendado)
1. Conecte seu repositório GitHub
2. Adicione a variável `BOT_TOKEN` no painel
3. Deploy automático será realizado

### Render
1. Conecte seu repositório GitHub
2. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn bot:app`
3. Adicione a variável `BOT_TOKEN`

## 📝 Variáveis de Ambiente

| Variável | Descrição | Obrigatório |
|----------|-----------|-------------|
| `BOT_TOKEN` | Token do bot do Telegram | ✅ |
| `PORT` | Porta do servidor (automática) | ❌ |
| `FLASK_ENV` | Ambiente Flask | ❌ |

## 🔒 Segurança

- ✅ Token protegido por variáveis de ambiente
- ✅ Não armazena dados sensíveis
- ✅ Validação de entrada de dados
- ✅ Logs de segurança

## 💡 Como Usar

1. **Inicie**: Digite `/start` para começar
2. **Questionário**: Responda as perguntas sobre seus dados
3. **Relatório**: Receba análise completa do IMC e orientações
4. **Chat**: Continue conversando para dúvidas específicas

## 📊 Comandos Disponíveis

- `/start` - Inicia o bot e coleta de dados
- Respostas automáticas para perguntas sobre:
  - Dieta e alimentação
  - Técnicas cirúrgicas
  - Recuperação e pós-operatório
  - Critérios médicos

## 🤝 Contribuição

1. Faça fork do projeto
2. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
3. Commit suas mudanças: `git commit -m 'Adiciona nova funcionalidade'`
4. Push para a branch: `git push origin feature/nova-funcionalidade`
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## ⚠️ Disclaimer

Este bot fornece informações gerais sobre cirurgia bariátrica e não substitui consulta médica profissional. Sempre consulte um cirurgião bariátrico qualificado para orientações específicas.

## 📞 Contato

- **Desenvolvedor**: Seu Nome
- **Email**: seu.email@exemplo.com
- **GitHub**: [@seu-usuario](https://github.com/seu-usuario)

---

Feito com ❤️ para ajudar pessoas na jornada da cirurgia bariátrica