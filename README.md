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

- O app abre como um **widget compacto** que fica por cima das outras janelas;
- **Arraste o arquivo** (ou clique para escolher): ele fica **anexado**, esperando. Escreva as instruções se quiser e clique em **▶ Formatar** (ou tecle Enter no campo de instruções). Nada começa sozinho — assim dá tempo de escrever o que precisa;
- Durante o processamento há um botão **✕ Cancelar**; nada é gravado se você cancelar;
- O rodapé mostra o **saldo da conta OpenRouter**, atualizado depois de cada documento;
- O botão **⤢** alterna para o modo janela completa, com **histórico** (custo por documento incluído) e **configurações**;
- O campo *"Instruções adicionais"* é opcional: use para pedidos pontuais, como "não mexa no terceiro parágrafo" ou "assinatura como Gerente";
- **Vários arquivos de uma vez**: solte quantos quiser — eles entram numa fila e são processados em sequência;
- Ao final, o botão **📂 Abrir pasta** leva direto aos arquivos gerados, e **🔁 Refazer com a instrução acima** reprocessa o mesmo documento com uma nova instrução, sem procurar o arquivo de novo.

## 💬 Assistente (chat)

No topo do painel esquerdo há um alternador **Formatador / Assistente**. O assistente é um chat comum, com **conversa persistente** (continua de onde parou mesmo depois de fechar), que sabe:

- **conversar** e ajudar a redigir, resumir e revisar textos;
- **ler anexos**: `.docx`, `.xlsx`, `.pdf`, `.txt` e **imagens** — dá para fotografar um documento e pedir "transcreva" (OCR pelo próprio modelo de visão);
- **buscar na internet**: ligue o interruptor **🌐** ao lado do Enviar e a pergunta é respondida com informação atual, listando as **fontes consultadas** ao final. Custa cerca de **US$ 0,007 por pergunta** (busca da OpenRouter, até 5 resultados), por isso fica desligado por padrão — a preferência é lembrada;
- **gerar imagens** (via `bytedance-seed/seedream-5-0-lite`, ~US$ 0,035 por imagem);
- **editar planilhas Excel por linguagem natural**: anexe o `.xlsx` e peça *"crie uma coluna com o custo por pessoa e destaque o cabeçalho"*.

Sobre as planilhas, uma decisão de segurança importante: **a IA nunca executa código**. Ela devolve uma lista de operações conhecidas (escrever célula, fórmula, preencher abaixo, formato, formato numérico, largura, congelar painéis) que o app aplica com openpyxl — e sempre numa **cópia** (`_EDITADO.xlsx`), preservando o arquivo original.

## 📋 Aba Formulários

Além de formatar relatórios prontos, o app **preenche modelos**. Um modelo é um documento do serviço — com timbre e assinatura — onde os lugares a preencher estão marcados com chaves duplas:

```
Usuário(a): {{nome}}
Encaminhado para: {{destino}}
Motivo: {{motivo}}
```

Importe o modelo uma vez (botão *Importar…*) e o app monta um campo para cada marcador. Daí há dois caminhos:

- **preencher campo a campo**, ou
- **colar as anotações soltas** ("Caroliny, 27 anos, encaminhar pro CAPS Vila Matilde por causa do acompanhamento em saúde mental, tem medida protetiva") e clicar em **Preencher com IA** — ela distribui a informação nos campos certos, usando *somente* o que está nas anotações, sem inventar nada. Os campos ficam editáveis para conferência antes de gerar.

O documento sai com toda a formatação, timbre e assinatura do modelo preservados.

### Posição e tamanho na tela

O widget é uma janela normal: **arraste pela barra de título** para onde quiser e **redimensione pelas bordas** (mínimo 330×480). O app **lembra onde ficou e de que tamanho** — e guarda isso separadamente para cada modo, então o widget pode morar pequeno num canto enquanto o modo janela abre grande e centralizado. Se o monitor onde ela estava for desconectado, a posição inválida é descartada e a janela volta ao padrão.

### Andamento e resumo

O painel **Andamento** aparece nos dois modos — inclusive no widget compacto — que mostra cada etapa em tempo real (lendo, conferindo datas, corrigindo, gerando, verificando) e, ao final, um **resumo em texto**: perfil aplicado, parágrafos corrigidos, custo, resultado da conferência, avisos e os arquivos gerados. O botão *Copiar resumo* leva tudo para a área de transferência.

### Comandos pelo campo de instruções

O campo aceita, além de pedidos sobre o texto, alguns comandos que o app executa e remove antes de enviar à IA:

| O que escrever | O que acontece |
|---|---|
| `salvar na área de trabalho` | muda a pasta de saída só daquele arquivo |
| `lembrar: a psicóloga do serviço é a Bianca` | guarda o fato na memória institucional |
| `proteger: Nhocuné, Vila Reencontro` | acrescenta aos termos que a IA nunca corrige |

Tudo pode vir junto de instruções normais: *"salvar na área de trabalho e manter o terceiro parágrafo"* faz as duas coisas.

### Atualizações automáticas

O app confere as *Releases* deste repositório ao abrir. Havendo versão nova, aparece uma faixa **"⬆ Atualizar para a versão X"** — um clique baixa, substitui o programa e reabre sozinho. Dá para desligar o aviso ou procurar atualização manualmente em *Configurações*.

### Onde salvar os arquivos gerados

Três modos em *Configurações*: **mesma** pasta do original (padrão), uma pasta **fixa** escolhida, ou **perguntar** a cada arquivo.

Além disso, dá para pedir em português no campo de instruções, valendo só para aquele arquivo:

- *"salvar na área de trabalho"*
- *"salvar em Documentos"* / *"salvar na pasta Relatórios 2026"*
- *"salvar em C:\Users\...\Casos"*

O pedido de pasta é interpretado pelo app e **removido** antes de o texto ir para a IA — o resto da instrução continua valendo: *"salvar na área de trabalho e manter o terceiro parágrafo"* salva no Desktop e passa "manter o terceiro parágrafo" para a revisão.

### Citações de outros documentos (itálico)

Trechos **copiados de outro documento** — o histórico de outro serviço, um parecer, um despacho — costumam vir colados em itálico. O app detecta esses blocos (itálico, fora de lista, em sequência de três parágrafos ou mais) e **mantém o itálico**, que é o que identifica o trecho como citação.

O texto em si é **revisado normalmente**: ortografia, acentuação e pontuação são corrigidas como em qualquer outro parágrafo, e as mudanças aparecem no diff. O que não muda é a marca visual da citação. Um aviso informa quantos parágrafos foram tratados assim.

### Completude da revisão e segunda passada

Modelos de linguagem às vezes devolvem um parágrafo intacto no meio de um lote grande — não porque esteja correto, mas por "preguiça". O app trata isso em três camadas:

1. **Lotes menores** (12 parágrafos) e instrução explícita de revisar todos até o último;
2. **Detector local, sem IA**: nos parágrafos que voltaram sem nenhuma alteração, procura erros evidentes — acentuação faltando em palavras comuns (`nao`, `familia`, `saude`, `situacao`…), espaços duplicados, espaço antes de pontuação, minúscula depois de ponto, palavra repetida, falta de pontuação final, horário fora do padrão;
3. **Segunda passada**: os parágrafos suspeitos voltam para a IA num pedido focado, com as pendências detectadas em anexo. São poucos, então custa centavos.

Ao final, o resumo mostra a **completude** — *"Completude da revisão: 99% · corrigidos: 49 · sem alteração: 26 · citações preservadas: 0"* — e lista, com número do parágrafo e trecho, o que ficou sem revisão apesar de aparentar pendência, dizendo o motivo (devolvido sem alteração, correção revertida por alterar números, citação preservada).

O detector foi calibrado contra relatórios reais: encontra 22 pendências no original de um relatório de 75 parágrafos e **zero falsos positivos** no mesmo texto já revisado à mão. Ainda assim, ele acha erros *evidentes* — não substitui a leitura final.

Dá para desligar a segunda passada em *Configurações*.

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
| `app/forms.py` | modelos de formulário: detecta `{{campos}}`, preenche preservando o layout e distribui anotações com IA |
| `app/comandos.py` | comandos escritos no campo de instruções (lembrar / proteger) |
| `app/outdir.py` | resolve a pasta de saída (config + pedido em português nas instruções) |
| `app/updater.py` | verifica Releases, baixa e substitui o executável |
| `app/main.py` / `settings.py` | interface (widget/janela), onboarding e preferências |

Salvaguardas: a IA só vê texto (nunca o arquivo); números alterados são revertidos automaticamente; e uma autoverificação confere que **aceitar todas as revisões do diff reproduz exatamente a versão final** antes de salvar.

*Nenhum documento real é incluído neste repositório.*
