# Formatador de Relatórios — Planejamento do Projeto

**App desktop em Python (Windows) que recebe um documento por drag & drop e devolve, no padrão da casa, a versão final formatada + a versão com alterações rastreadas (diff), usando IA via OpenRouter para correção de ortografia e coerência sem alterar o conteúdo.**

---

## 1. Visão geral

| Item | Decisão |
|---|---|
| Plataforma | Windows (executável `.exe` único, sem instalar Python) |
| Interface | 2 modos com botão de alternância — **padrão: widget compacto** sempre-por-cima; modo janela completa opcional |
| Entrada | Drag & drop (ou clique para escolher) de `.docx` e `.xlsx` |
| Saída padrão (fixa) | `NOME_FINAL.docx` + `NOME_ALTERACOES_RASTREADAS.docx`, salvos ao lado do arquivo original |
| Extras opcionais | PDF da versão final; campo "instruções adicionais" para pedidos pontuais |
| IA | OpenRouter (chave da usuária, pré-pago ~US$ 5); modelo padrão Claude Sonnet, configurável |
| Distribuição | Repositório próprio no GitHub + GitHub Actions compila o `.exe` e publica em *Releases* |
| Manutenção | Zero: app estático; atualização = baixar novo `.exe` da release |

## 2. Experiência de uso (UX)

### 2.1 Onboarding (primeira execução)
Assistente de 3 passos, visual limpo:
1. **Boas-vindas** — o que o app faz, em uma frase, com ilustração do fluxo (arquivo → duas saídas).
2. **Chave OpenRouter** — campo para colar a chave, com link direto "como criar minha chave e adicionar créditos (passo a passo)" e botão **Testar conexão** que valida a chave na hora e mostra o saldo. A chave fica salva localmente (pasta do usuário, nunca sai do computador além da chamada à API).
3. **Preferências iniciais** — pasta de saída (padrão: mesma pasta do arquivo), gerar PDF sempre/nunca/perguntar, e pronto.

Depois disso, o app nunca mais pergunta nada — abre direto no widget.

### 2.2 Modo widget (padrão)
- Janelinha compacta (~300×220 px), cantos arredondados, sempre por cima das outras janelas (configurável).
- Conteúdo: área de drop grande ("Solte o relatório aqui"), campo discreto "Instruções adicionais (opcional)" e o botão de alternância para o modo janela.
- Durante o processamento: barra de progresso com etapas legíveis ("Lendo documento… Corrigindo texto… Gerando diff… Salvando").
- Ao concluir: aviso de sucesso + botão **Abrir pasta** com os arquivos gerados.

### 2.3 Modo janela completa
Tudo do widget, mais:
- **Histórico** dos últimos documentos processados (nome, data, custo estimado da chamada, botão reabrir pasta).
- **Configurações**: chave da API, modelo de IA, pasta de saída, PDF, comportamento sempre-por-cima, tema claro/escuro.
- **Fila em lote**: soltar vários arquivos de uma vez e processar em sequência (útil em semana de fechamento de relatórios).

### 2.4 Instalação no PC dela
1. Baixar `Formatador.exe` da página de Releases do GitHub (link direto no README).
2. Copiar para qualquer pasta e criar atalho na área de trabalho (o README ensina; opcionalmente um pequeno `instalar.bat` cria o atalho sozinho e fixa na barra de tarefas).
3. Abrir, passar pelo onboarding de 3 passos, usar.

> Aviso conhecido: por não ser assinado digitalmente, o Windows SmartScreen mostra alerta na primeira execução ("Executar assim mesmo"). Documentado no README com captura de tela.

## 3. O que o app faz por dentro (pipeline)

### 3.1 Documentos `.docx`
1. Abre o `.docx` (ZIP + XML) e extrai os parágrafos do corpo, **preservando intactos cabeçalho timbrado, rodapé, numeração de páginas e imagens de assinatura**.
2. Envia apenas o texto à IA com instrução rígida: *corrigir somente ortografia, gramática, pontuação e coerência; proibido alterar fatos, datas, nomes, números, valores, diagnósticos ou o sentido; devolver parágrafo a parágrafo em JSON*. As "instruções adicionais" da usuária entram como orientação extra.
3. Valida a resposta (mesmo número de parágrafos; se a IA fugir do formato, repete a chamada; números e datas do original são conferidos programaticamente contra o corrigido — qualquer divergência não solicitada é rejeitada e refeita).
4. Gera a **versão final**: formatação padronizada (Times New Roman 12, justificado com recuo de 1ª linha, espaçamento 1,5, título centralizado, data à direita, rótulos em negrito, listas com marcadores, bloco de assinatura centralizado) — o mesmo padrão dos 4 relatórios já feitos.
5. Gera a **versão diff**: alterações rastreadas nativas do Word (inserções sublinhadas / exclusões riscadas, navegáveis na aba Revisão), calculadas por comparação palavra a palavra em código determinístico — a IA não participa do diff. Última página traz a nota das mudanças de formatação.
6. **Autoverificação**: o app "aceita" o diff internamente e confere que o resultado é idêntico à versão final; só então salva os dois arquivos.
7. Opcional: exporta PDF da versão final (via Word instalado, fidelidade total; sem Word, conversor interno com fidelidade alta).

### 3.2 Planilhas `.xlsx`
1. Lê as células de texto (números, fórmulas e formatação ficam travados — o código não deixa a IA tocá-los).
2. Corrige ortografia/coerência dos textos.
3. Saídas: `NOME_FINAL.xlsx` (corrigida) + `NOME_ALTERACOES.xlsx` (células alteradas realçadas em amarelo + aba "Alterações" com antes → depois de cada célula).

## 4. Privacidade e cuidado com dados (importante para o serviço dela)

Os relatórios contêm dados pessoais sensíveis (saúde, violência, menores). O planejamento prevê:
- Processamento local de tudo, exceto o texto enviado à API para correção.
- README orienta a ativar na conta OpenRouter a opção de **não usar os dados para treinamento** e restringir a provedores com política de não-retenção (configurável no app pela lista de modelos).
- Nenhum texto é armazenado pelo app além do histórico local (que pode ser desativado); a chave fica só no computador dela.

## 5. Estrutura do repositório GitHub

```
formatador-relatorios/
├── app/                  # código Python
│   ├── main.py           # janela, widget, alternância de modos
│   ├── onboarding.py     # assistente de 3 passos
│   ├── docx_engine.py    # extração, formatação, diff/tracked changes
│   ├── xlsx_engine.py    # modo planilha
│   ├── ai_client.py      # OpenRouter (chamadas, validação, custo)
│   └── settings.py       # preferências locais
├── assets/               # ícone, ilustrações
├── .github/workflows/build.yml   # compila o .exe a cada versão (PyInstaller) e publica Release
├── README.md             # instalação passo a passo com imagens (inclui criar chave OpenRouter)
└── PLANEJAMENTO.md       # este documento
```

Stack: Python 3.12 · CustomTkinter (UI moderna, tema claro/escuro) · tkinterdnd2 (drag & drop) · lxml (XML do docx) · openpyxl (xlsx) · requests (OpenRouter) · PyInstaller (empacotamento) — todas bibliotecas maduras e gratuitas.

## 6. Mini roadmap

| Fase | Entrega | Conteúdo |
|---|---|---|
| **1. Motor** | biblioteca testável | Pipeline docx completo (extração → IA → final + diff + autoverificação), testado com os 4 relatórios reais desta conversa como casos de teste |
| **2. App** | `Formatador.exe` v0.1 | Widget + janela completa, alternância, onboarding da chave, processamento docx, salvar ao lado do original |
| **3. Distribuição** | repositório + Release v1.0 | GitHub Actions compilando o `.exe`, README ilustrado, `instalar.bat`, teste de instalação limpa |
| **4. Extras** | v1.1 | PDF opcional, modo `.xlsx`, fila em lote, histórico com custo por documento |
| **5. Refino** | v1.2 | Tema escuro, ajustes de UX com feedback real dela após 1–2 semanas de uso |

Fases 1–3 formam o mínimo utilizável (ela já trabalha com ele); 4 e 5 vêm logo atrás sem quebrar nada.

## 7. Ideias adicionais (opcionais, decidir depois)

- **Perfil da instituição**: as regras de formatação (fonte, assinatura "Gerente" vs "Equipe Técnica", margens) ficam num arquivo de perfil editável — se o serviço mudar o padrão ou ela trabalhar com dois padrões, é só criar outro perfil e escolher no drop.
- **Custo visível**: mostrar após cada documento o custo real da chamada (ex.: "US$ 0,06 — saldo estimado: US$ 4,71") para nunca haver surpresa.
- **Arrastar direto do e-mail/WhatsApp Web**: aceitar também quando ela arrastar um anexo direto do navegador.
- **Botão "Reprocessar com instrução"**: se não gostar de algo, reabre o último arquivo com uma instrução nova sem procurar o arquivo de novo.
- **Verificação de nomes próprios**: lista opcional de nomes/termos da instituição (CREAS, CAPS, nomes de técnicos) que a IA nunca deve "corrigir".

---

*Próximo passo quando você autorizar: Fase 1 (motor), usando os quatro relatórios desta conversa como bateria de testes. Para a Fase 3 vou precisar do GitHub conectado à sessão (ou um token) para criar o repositório no seu usuário.*
