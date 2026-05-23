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

https://buymeacoffee.com/ptlegion

Créditos: RɆβɆŁŞØɄŁ

