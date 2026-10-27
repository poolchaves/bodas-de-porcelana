# Bodas de Porcelana — Marcelle & Paulo Chaves

Aplicação Flask com convite individual por casal, confirmação de 1 ou 2 pessoas, painel administrativo, exportação CSV, links WhatsApp, QR Code e fotografia oficial incorporada.

## Publicar na internet (Render + PostgreSQL)

1. Crie um repositório **privado** no GitHub e envie os arquivos desta pasta (não apenas o ZIP).
2. Entre em https://dashboard.render.com e escolha **New > Blueprint**; conecte o repositório. O arquivo `render.yaml` configura o serviço e o banco PostgreSQL. Confira os custos e disponibilidade de planos antes de confirmar.
3. Configure a variável `ADMIN_PASSWORD` com uma senha forte e exclusiva. **Não compartilhe a senha em conversas nem coloque no repositório.** O Render gera automaticamente `SECRET_KEY` e fornece `DATABASE_URL`.
4. Aguarde a publicação e copie a URL HTTPS exibida pelo Render, por exemplo `https://seu-servico.onrender.com` (exemplo, não é um endereço existente).
5. Abra `https://SEU-ENDERECO/admin`, faça login e cadastre os nomes dos casais. O painel oferece os links individuais, WhatsApp e QR Codes.
6. Abra um convite real no celular e verifique os dois botões externos, inclusive a validade do link QRToken, antes de enviar os convites.

**Importante:** não use SQLite em uma hospedagem sem armazenamento persistente. O Blueprint usa PostgreSQL para preservar as respostas. Se o serviço for movido para outra hospedagem, configure `DATABASE_URL`, `SECRET_KEY`, `ADMIN_PASSWORD` e `COOKIE_SECURE=1`.

## Executar localmente (computador)

Requer Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export SECRET_KEY='crie-uma-chave-aleatoria-longa'
export ADMIN_PASSWORD='defina-uma-senha-forte'
python app.py
```

Abra http://127.0.0.1:5000/admin. O banco SQLite local será criado automaticamente.

## Observações

- Os dados do evento já estão pré-cadastrados no código.
- O link de acesso ao condomínio é externo, e seu funcionamento depende do fornecedor QRToken.
- Os convidados não precisam criar conta; os links individuais são difíceis de adivinhar, mas podem ser compartilhados por quem os recebe. Evite divulgar publicamente links pessoais.
- O sistema permite editar respostas no painel administrativo, mesmo depois do prazo; convidados só podem responder até 1º/11/2026, 23h59 (Porto Velho).
- CSV abre no Excel. A foto é `static/casal.png`.
- Para um lançamento público de maior escala, recomenda-se adicionar rate limiting, backups automatizados e monitoramento; o projeto é uma primeira versão funcional para um evento privado.
