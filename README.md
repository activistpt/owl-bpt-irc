# 🦉 OWL Bot - PTnet IRC

Bot IRC para a rede PTnet com comandos utilitários.

## Ficheiros

- `ptnet_irc.py` - Bridge IRC (conecta ao PTnet, gateway de mensagens)
- `irc_daemon.py` - Daemon principal (processa comandos, envia respostas)

## Comandos

| Comando | Descrição |
|---------|-----------|
| `!help` | Lista de comandos |
| `!quote` | Citação aleatória |
| `!notice <nick>` | Envia quote privada + anuncia no #deep-web |
| `!notice <canal>` | Envia quote para o canal (PRIVMSG) |
| `!wiki <termo>` | Pesquisa Wikipédia |
| `!img <descrição>` | Gera imagem |
| `!meteo <cidade>` | Meteorologia |
| `!crypto <moeda>` | Preço de crypto |

## Deploy

```bash
python3 ptnet_irc.py  # Terminal 1: IRC bridge
python3 irc_daemon.py  # Terminal 2: Daemon
```

## Arquitetura

Comunicação via ficheiros JSONL:
- `~/.hermes/irc/incoming.jsonl` - Mensagens recebidas do IRC
- `~/.hermes/irc/outgoing.jsonl` - Respostas para enviar ao IRC

🎯 Objetivo
Criar um bot útil, estável e divertido para a comunidade IRC portuguesa, especialmente na PTnet, combinando ferramentas clássicas com tecnologias modernas (IA, APIs, etc.).

⚠️ Requisitos
Python 3.8+
Conta na PTnet (nick registado recomendado)
Dependências listadas em requirements.txt

🤝 Contribuições
Pull Requests são bem-vindas!
Podes ajudar a:
Adicionar novos comandos
Melhorar a estabilidade da conexão IRC
Integrar mais APIs
Corrigir bugs

📜 Licença
Este projeto está sob a licença MIT.
Feito com ❤️ para a comunidade PTnet

https://buymeacoffee.com/ptlegion

Créditos: RɆβɆŁŞØɄŁ

