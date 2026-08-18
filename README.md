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
3. Em **Credits**, adicione créditos — **US$ 5 rendem de 50 a 150 relatórios** (cada documento custa entre US$ 0,03 e 0,10);
4. Cole a chave no app e clique em **Testar conexão**.

> **Privacidade (importante):** os relatórios podem conter dados sensíveis. Na sua conta OpenRouter, acesse *Settings → Privacy* e **desative** o uso dos seus dados para treinamento de modelos.

## 🖥️ Usando

- O app abre como um **widget compacto** que fica por cima das outras janelas — arraste o arquivo pra ele e pronto;
- O botão **⤢** alterna para o modo janela completa, com **histórico** (custo por documento incluído) e **configurações**;
- O campo *"Instruções adicionais"* é opcional: use para pedidos pontuais, como "não mexa no terceiro parágrafo" ou "assinatura como Gerente";
- Ao final, o botão **📂 Abrir pasta** leva direto aos arquivos gerados.

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
| `app/ai_client.py` | chamadas à OpenRouter com validação de formato e custo por request |
| `app/worker.py` | orquestração em thread + PDF opcional via Word (docx2pdf) |
| `app/main.py` / `settings.py` | interface (widget/janela), onboarding e preferências |

Salvaguardas: a IA só vê texto (nunca o arquivo); números alterados são revertidos automaticamente; e uma autoverificação confere que **aceitar todas as revisões do diff reproduz exatamente a versão final** antes de salvar.

*Nenhum documento real é incluído neste repositório.*
