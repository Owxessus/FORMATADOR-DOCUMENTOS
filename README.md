# 📄 Formatador de Relatórios

App de desktop (Windows) que transforma relatórios institucionais brutos em documentos profissionais. Você **arrasta o `.docx` para a janelinha** e ele devolve, na mesma pasta do arquivo:

- **`NOME_FINAL.docx`** — versão formatada no padrão institucional (Times New Roman 12, texto justificado com recuo, espaçamento 1,5, título centralizado, cabeçalho timbrado e assinaturas **preservados do original**);
- **`NOME_ALTERACOES_RASTREADAS.docx`** — a mesma versão com **alterações rastreadas do Word**: tudo que foi corrigido aparece riscado/sublinhado, para revisar mudança por mudança na aba *Revisão*.

A correção de ortografia e coerência é feita por IA (via [OpenRouter](https://openrouter.ai)), com regras rígidas: **fatos, datas, nomes, números, siglas e o sentido do texto nunca são alterados** — e o app confere isso por código, revertendo qualquer alteração indevida de números.

Também aceita planilhas `.xlsx`: devolve a planilha corrigida + uma cópia com as células alteradas realçadas em amarelo e uma aba "Alterações" (antes → depois).

---

## 🚀 Instalação (computador da usuária)

1. Baixe o **`Formatador.exe`** na página de [**Releases**](../../releases/latest);
2. Copie para uma pasta de sua preferência (ex.: `Documentos\Formatador`);
3. (Opcional) Coloque o `instalar.bat` na mesma pasta e dê dois cliques — ele cria o atalho na Área de Trabalho;
4. Abra o app. Na primeira vez o Windows pode mostrar *"O Windows protegeu o computador"* — clique em **Mais informações → Executar assim mesmo** (o aviso aparece porque o executável não é assinado digitalmente; é normal em apps pessoais).

## 🔑 Configurando a chave OpenRouter (uma única vez)

O próprio app guia esse processo no primeiro uso. Em resumo:

1. Crie uma conta gratuita em [openrouter.ai](https://openrouter.ai);
2. Em **Keys**, clique em *Create Key* e copie a chave (`sk-or-v1-…`);
3. Em **Credits**, adicione créditos. Há três modelos no menu de configurações, do mais barato ao mais caro: **GPT-5.6 Luna** (esforço máximo, ~US$ 0,005/relatório), **Gemini 3.7 Flash** (padrão, ~US$ 0,01) e **Claude Sonnet 5** (~US$ 0,05). Com o padrão, **US$ 5 rendem centenas de documentos**;
4. Cole a chave no app e clique em **Testar conexão**.

> **Privacidade (importante):** os relatórios podem conter dados sensíveis. Na sua conta OpenRouter, acesse *Settings → Privacy* e **desative** o uso dos seus dados para treinamento de modelos.

## 🖥️ Usando

- O app abre como um **widget compacto** que fica por cima das outras janelas — arraste o arquivo pra ele e pronto;
- O botão **⤢** alterna para o modo janela completa, com **histórico** (custo por documento incluído) e **configurações**;
- O campo *"Instruções adicionais"* é opcional: use para pedidos pontuais, como "não mexa no terceiro parágrafo" ou "assinatura como Gerente";
- **Vários arquivos de uma vez**: solte quantos quiser — eles entram numa fila e são processados em sequência;
- Ao final, o botão **📂 Abrir pasta** leva direto aos arquivos gerados, e **🔁 Refazer com a instrução acima** reprocessa o mesmo documento com uma nova instrução, sem procurar o arquivo de novo.

### Conferência automática de datas

Antes de enviar qualquer coisa à IA, o app confere as datas do documento **por código** e avisa (sem alterar nada) quando encontra:

- uma data posterior à data do relatório, sem indicação de agendamento;
- um ano isolado que destoa da sequência ao redor — o erro de digitação clássico (um "2026" no meio de fatos de 2021).

Os avisos aparecem junto ao resultado, para conferência antes do envio.

### Memória base (aba *Memória*)

Guarda o que é estável no serviço e não deveria ser redigitado a cada relatório — fica em `memoria.json`, separado das preferências, e **sobrevive às atualizações do app**:

- **Blocos institucionais**: os textos oficiais (descrição do serviço, estrutura física, quadro de funcionários). Quando um relatório traz esse trecho com diferenças, o app avisa;
- **Perfis de documento**: *Relatório Técnico*, *Relatório de Ocorrência* e *Relatório de Gerência* — cada um com sua assinatura (Equipe Técnica × Gerente) e instruções fixas. O perfil é detectado pelo título do documento ou escolhido no menu acima da área de drop.

### Busca nos relatórios (aba *Busca*)

Todo documento processado entra num índice local pesquisável, e a aba permite **indexar pastas antigas** de uma vez. A busca entende flexões e acentos: procurar por *"convulsão"* encontra *"convulsivos"*, e *"conselho tutelar"* encontra o trecho mesmo com erro de digitação no original. O índice fica só no computador — nada é enviado para fora.

### Termos protegidos

Em *Configurações* há uma lista de termos que a IA **nunca** pode alterar — já vem preenchida com as siglas do setor (CREAS, CAPS, SAMU, AVCB, CID, CREMESP…). Acrescente nomes de funcionários, unidades de saúde, bairros e medicamentos recorrentes: eles passam intactos pela revisão.

Depois, é só abrir a versão `ALTERACOES_RASTREADAS` no Word e revisar: cada correção pode ser aceita ou rejeitada individualmente (aba *Revisão* → *Aceitar/Rejeitar*).

## 🔧 Para desenvolvedores

```bash
pip install -r requirements.txt
python app/main.py
```

O executável é compilado automaticamente pelo GitHub Actions: criar uma tag `v*` (ex.: `v1.0.0`) gera uma Release com o `Formatador.exe`.

```bash
git tag v1.0.0 && git push --tags
```

### Arquitetura

| Módulo | Papel |
|---|---|
| `app/docx_engine.py` | extrai parágrafos preservando timbre/assinaturas, reconstrói o docx formatado e gera o diff com tracked changes nativos (determinístico) |
| `app/xlsx_engine.py` | modo planilha (números e fórmulas travados em código) |
| `app/checks.py` | verificações determinísticas (consistência de datas, blocos canônicos) |
| `app/memory.py` | memória base persistente: blocos institucionais e perfis de documento |
| `app/archive.py` | índice pesquisável (SQLite FTS5) com busca por radical e sem acento |
| `app/ai_client.py` | chamadas à OpenRouter (padrão: `google/gemini-3.7-flash`) com validação de formato, termos protegidos e custo por request |
| `app/worker.py` | orquestração em thread + PDF opcional via Word (docx2pdf) |
| `app/main.py` / `settings.py` | interface (widget/janela), onboarding e preferências |

Salvaguardas: a IA só vê texto (nunca o arquivo); números alterados são revertidos automaticamente; e uma autoverificação confere que **aceitar todas as revisões do diff reproduz exatamente a versão final** antes de salvar.

*Nenhum documento real é incluído neste repositório.*
