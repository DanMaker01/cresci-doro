# Crescidoro

Timer Pomodoro em pygame com **modo de crescimento** (o pomodoro aumenta X% a cada
pomodoro concluído) e **histórico editável** com gráfico interativo e heatmap.

## Rodar

```bash
pip install -r requirements.txt
python main.py
```

## Funcionalidades

**Timer**
- Pomodoro / Break / Long; a duração fica sob cada aba - clique e digite `25` ou `25:30`.
- Crescidoro: a cada pomodoro concluído *naturalmente*, o próximo cresce `X%`.
- Long break automático a cada `N` pomodoros (0 desativa). Os pontinhos sob o
  timer mostram o progresso do ciclo.
- Tempo restante no título da janela.

**Motivo do fim** - todo registro guarda por que terminou:

| motivo   | quando                                                        |
|----------|---------------------------------------------------------------|
| natural  | o tempo chegou a zero                                         |
| pausado  | FINALIZAR ou troca de modo com a sessão em andamento          |
| fechado  | app fechado com a sessão em andamento (inclusive crash: a sessão é salva a cada 10 s e recuperada na próxima abertura) |
| manual   | registro adicionado à mão                                     |

Registros pausados/fechados aparecem em tom mais apagado no gráfico.

**Histórico**
- **barras**: em cada dia, 3 barras lado a lado - pomodoro, break e long. Cada
  barra é subdividida pelos registros daquele tipo no dia (o mais antigo embaixo).
- Clique num registro → menu: **editar…**, **duplicar**, **novo registro neste
  dia**, **remover**. Clique num espaço vazio do dia → **novo registro…**.
- Editar/criar abre um diálogo com tipo, data, início, duração (`25`, `25:30`
  ou `1:05:00`) e motivo do fim.
- **linha**: total diário por tipo. **mapa**: heatmap estilo GitHub do último
  ano de foco (53 semanas × dom–sáb, 5 níveis por quartil, resumo com total,
  dias ativos, média, melhor dia e maior sequência). Clique num dia para
  abri-lo no gráfico.
- **14d**: janela de 14 dias com scroll horizontal por todo o histórico.
  **total**: todo o histórico na tela.
- Dias sem registro aparecem zerados; os pontos coloridos ligam/desligam cada tipo.
- **desfazer** (Ctrl+Z) para qualquer alteração no histórico.

## Atalhos

| tecla               | ação                                   |
|---------------------|----------------------------------------|
| Espaço              | iniciar / pausar                       |
| F                   | finalizar a sessão agora               |
| 1 · 2 · 3           | pomodoro · break · long                |
| C                   | liga/desliga crescidoro                |
| ← → (Shift = 7 dias)| rolar o gráfico                        |
| Home / End          | início / fim do histórico              |
| roda do mouse       | rolar o gráfico                        |
| N                   | novo registro                          |
| M                   | alterna mapa / gráfico                 |
| Ctrl+Z              | desfazer                               |
| Enter / Esc         | salvar / fechar (diálogo e menu)       |
| Tab                 | próximo campo                          |

## Dados

Ficam ao lado do executável (ou na raiz do projeto em dev). Para outro local,
defina a variável `CRESCIDORO_DATA`.

- `historico_pomodoro.json` - `{"versao": 2, "registros": [{id, estado, inicio, duracao_s, motivo}]}`.
  O formato antigo (lista com `timestamp`) é migrado automaticamente e uma cópia
  é guardada em `historico_pomodoro.json.v1.bak`.
- `config_tempos.json` - durações, crescidoro, ciclo e preferências do gráfico
  (compatível com o arquivo antigo).
- Gravação atômica: um fechamento no meio da escrita não corrompe os arquivos.

## Estrutura

```
main.py                    ponto de entrada
crescidoro/
  models.py                Registro, tipos e motivos
  storage.py               histórico (CRUD + desfazer), config, checkpoint da sessão
  timer.py                 máquina de estados do timer (sem pygame)
  stats.py                 séries diárias, heatmap, formatação (sem pygame)
  paths.py                 caminhos de recursos e dados
  ui/
    app.py                 janela, layout e loop principal
    chart.py               3 barras/dia subdivididas por registro, scroll, hover
    heatmap.py             heatmap anual estilo GitHub
    dialog.py              diálogo de editar/criar registro
    widgets.py, theme.py   botões, campos, menu popup, tooltip, cores e fontes
tests/                     pytest (núcleo + fumaça da interface)
```

## Testes

```bash
pip install pytest
python -m pytest
```

## Compilar (Windows)

```bash
pip install pyinstaller
pyinstaller main.spec
```

ou, sem o spec:

```bash
pyinstaller --onefile --windowed --name crescidoro --icon=icon.ico --add-data "sucesso.mp3;." --add-data "icon.ico;." main.py
```

O `.exe` sai em `dist/`. Os JSONs **não** são empacotados: o app lê/grava os
que estão ao lado do `.exe` (os seus atuais em `dist/` continuam valendo).

## Versão para celular (app web / PWA)

A pasta `web/` tem uma versão para celular feita em HTML/JS: mesma lógica
(crescidoro, ciclo de long break, motivo do fim), interface de toque, som,
vibração e funcionamento offline. O histórico fica **só no aparelho**
(armazenamento do navegador).

**Publicar (uma vez):**
1. No GitHub: *Settings → Pages → Build and deployment → Source: GitHub Actions*.
2. Faça push. O workflow `.github/workflows/pages.yml` publica a pasta `web/`
   em `https://<seu-usuario>.github.io/crescidoro/`.
   (Repositório privado precisa de plano pago para usar o Pages; se for o caso,
   deixe o repositório público ou hospede a pasta `web/` em outro lugar, como Netlify.)

**Instalar no Android:** abra o link no Chrome → menu ⋮ → *Adicionar à tela
inicial / Instalar app*. Ele abre em tela cheia, com ícone, e funciona sem internet.

**Uso:**
- Toque numa barra para editar, duplicar ou remover aquele registro; toque num
  dia para ver todos os registros dele. Arraste o gráfico para o lado para ver o passado.
- Toque no relógio (parado) ou na aba já selecionada para mudar a duração.
- Ajustes (ícone no canto): durações, crescidoro, long break, som, vibração,
  manter a tela ligada, notificação e **importar/exportar** o histórico
  (aceita o `historico_pomodoro.json` do PC; repetidos são ignorados).
- Se a página for fechada com o timer rodando, ao reabrir ele continua do ponto certo.

**Limitação:** com a tela apagada, o Android pode pausar o navegador e o som
pode não tocar na hora - por isso a opção "manter a tela ligada" vem ativada.

**Testar no PC:** `python -m http.server -d web 8000` e abra `http://localhost:8000`.

Ao alterar arquivos de `web/`, aumente `VERSAO` em `web/sw.js` para os celulares
pegarem a versão nova.
