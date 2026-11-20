<div align="center">

  <!-- Espaço para o logotipo do projeto. -->
  <h1>Monitoramento Meteorológico WS-2000</h1>

  <p>API local para acompanhar a estação Ambient Weather, consultar o histórico em unidades métricas e exportar as medições em CSV.</p>

  <p>
    <a href="#instalacao"><img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&amp;logoColor=white" alt="Python 3.12 ou superior"></a>
    <a href="#consultas"><img src="https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&amp;logoColor=white" alt="API com FastAPI"></a>
    <a href="#armazenamento"><img src="https://img.shields.io/badge/Banco_local-SQLite-003B57?logo=sqlite&amp;logoColor=white" alt="Banco local SQLite"></a>
    <a href="#postgresql"><img src="https://img.shields.io/badge/Migra%C3%A7%C3%A3o-PostgreSQL-4169E1?logo=postgresql&amp;logoColor=white" alt="Migração para PostgreSQL"></a>
  </p>

  <p>
    <a href="#instalacao">Desenvolvimento local</a> ·
    <a href="docs/DEPLOY_SESC.md">Implantação futura no SESC</a> ·
    <a href="#console">Conectar a estação</a> ·
    <a href="#simulador">Testar com o simulador</a> ·
    <a href="#consultas">Consultar a API</a>
  </p>
</div>

## Onde executar

| | DEV · computador pessoal | PROD · futura instalação no SESC |
| --- | --- | --- |
| Origem das medições | Simulador WS-2000 via loopback | Console físico pela LAN autorizada |
| SQLite | `data/weather-dev.db` | `data/weather.db` ou caminho escolhido pela TI |
| Acesso | Swagger local e dois serviços testáveis em portas distintas | Ingestão privada e leitor publicado por túnel HTTPS |
| Operação | Processos em primeiro plano, encerrados com Ctrl+C | Serviços do sistema, monitoramento e backup diário com réplica externa |
| Modelo de configuração | [.env.example](.env.example) | [production.env.example](deploy/production.env.example) |

A instalação atual é de desenvolvimento. Os passos para transferir a versão testada ao computador da instituição estão no [guia de implantação futura](docs/DEPLOY_SESC.md).

## O problema

O valor de chuva que o console envia a cada minuto pode ser o acumulado do dia. Somar essas leituras em uma planilha multiplicaria a chuva registrada. Uma transmissão repetida pelo Wi-Fi também pode parecer uma nova amostra. Para analisar o tempo em um período, é preciso saber o que cada sensor mediu, em qual unidade e em que instante.

## A solução

A WS-2000 envia as leituras por Wi-Fi para um computador da rede local. A API converte as unidades na chegada, registra os horários de medição e de recebimento em UTC e guarda uma observação por estação e instante de medição. Após a instalação, a coleta e o Swagger funcionam mesmo sem acesso à internet.

| Etapa | O que acontece |
| --- | --- |
| **Coleta** | O console reúne os sensores disponíveis e transmite os parâmetros por HTTP para `/data/report/`. |
| **Armazenamento** | O backend valida os campos, grava as medições em unidades métricas e conserva os parâmetros originais em `raw_payload` para auditoria. |
| **Consulta** | Pelo Swagger ou pela API REST, é possível conferir a última leitura, filtrar o histórico, calcular um resumo e baixar o período em CSV. |

## Sumário

- [Instalação no Windows ou Linux](#instalacao)
- [Configuração do console WS-2000](#console) e [ensaio com o simulador](#simulador)
- [Referência completa da API](#consultas) e [guia independente do frontend](docs/FRONTEND_INTEGRATION.md)
- [Contratos públicos](#consultas-públicas-rota-por-rota), [limites e segurança](#segurança-e-limites-de-acesso) e [respostas de erro](#respostas-de-erro)
- [Exemplos TypeScript](#guia-de-integração-com-react--typescript) e [contratos do serviço privado](#ingestão-e-diagnóstico-local)
- [Protocolo e regras de armazenamento](#armazenamento)
- [Configuração da rede local](#rede) e [diagnóstico](#diagnostico)
- [Testes automatizados](#testes) e [migração para PostgreSQL](#postgresql)
- [Organização do repositório](#estrutura) e [parceria](#parceria)

<a id="instalacao"></a>

## Instalação para desenvolvimento local

Use Python **3.12 ou superior** e rode o instalador a partir da raiz. Ele cria a `.venv` neste computador, instala as dependências e os testes, cria o `.env` a partir do modelo DEV na primeira execução e aplica as migrações à base configurada. A primeira instalação precisa de acesso ao índice de pacotes ou a um espelho local. Depois disso, a coleta simulada, as consultas e o Swagger funcionam offline.

| Ação | Windows · PowerShell | Linux · Bash |
| --- | --- | --- |
| Instalar DEV | `python scripts/install.py dev` | `python3 scripts/install.py dev` |
| Abrir a API combinada com Swagger | `.\scripts\start.ps1 dev` | `bash scripts/start.sh dev` |
| Iniciar somente a ingestão | `.\scripts\start.ps1 ingest` | `bash scripts/start.sh ingest` |
| Iniciar somente a consulta pública local | `.\scripts\start.ps1 public` | `bash scripts/start.sh public` |
| Executar a suíte | `.\.venv\Scripts\python -m pytest -q` | `.venv/bin/python -m pytest -q` |

Para explorar a API, inicie `dev` e abra o [Swagger local](http://127.0.0.1:8000/docs). Para testar a separação real, execute `ingest` e `public` em **dois terminais**. A ingestão atende em `127.0.0.1:8001` e o leitor em `127.0.0.1:8080`. O processo opcional de Swagger pode rodar ao lado dos dois na porta 8000. Todos leem o mesmo `.env` e a mesma base DEV. Esses comandos executam em primeiro plano com permissões de usuário comum.

Os arquivos de inicialização usam a raiz do projeto como diretório de trabalho. Para personalizar as portas, edite `DEV_PORT`, `INGEST_PORT` e `PUBLIC_PORT` no `.env` e reinicie o respectivo processo. Se a política local restringir scripts PowerShell, execute o equivalente na raiz, por exemplo `.\.venv\Scripts\python -m app.serve dev`.

Ao atualizar um checkout antigo, o instalador preserva o `.env` existente. Para adotar o perfil DEV, confira `APP_ENV=development`, `DATABASE_URL=sqlite:///./data/weather-dev.db` e `ALLOW_SIMULATED=true` antes de executar o instalador. As variáveis exportadas no terminal têm prioridade sobre o `.env`. Uma mudança de URL seleciona outro arquivo. O histórico anterior continua na base original.

<a id="simulador"></a>

## Conferir o fluxo com o simulador

Com `ingest` e `public` em execução, use um terceiro terminal na raiz. No Windows:

```powershell
.\.venv\Scripts\python scripts/simulate_station.py --samples 2 --interval 2 --field tempf=86
Invoke-RestMethod http://127.0.0.1:8080/api/v1/stations
```

No Linux:

```bash
.venv/bin/python scripts/simulate_station.py --samples 2 --interval 2 --field tempf=86
curl http://127.0.0.1:8080/api/v1/stations
```

O simulador usa a porta `INGEST_PORT` do `.env`, marca cada amostra com `dev_simulated=1` e aceita `--mac` e `--field NOME=VALOR`. Use o ID da lista para consultar `http://127.0.0.1:8080/api/v1/stations/{id}/latest` e conferir a temperatura externa de 30 °C. Para testar apenas o processo combinado com Swagger, forneça `--url http://127.0.0.1:8000` ao simulador. A produção vem com simulações desabilitadas. Exemplo de uma transmissão reproduzível, contra a instância de desenvolvimento:

```text
GET /data/report/?MAC=02%3A00%3A00%3A00%3A20%3A00&dateutc=2026-11-20+14%3A30%3A00&tempf=86&humidity=60&windspeedmph=12&dailyrainin=0.10&dev_simulated=1
```

A resposta padrão é HTTP 200 com texto `OK`. Em `/api/v1/stations/1/latest`, esses valores correspondem a 30 °C, 60%, 5,36448 m/s e 2,54 mm. Use o ID devolvido por `/api/v1/stations` se houver outras estações.

<a id="consultas"></a>

# Referência completa da API

| Método | Caminho | Serviço | Acesso | Finalidade |
|---|---|---|---|---|
| GET | `/api/v1/stations` | Público | Leitura anônima | Listar estações por ID |
| GET | `/api/v1/stations/{station_id}` | Público | Leitura anônima | Consultar identificação e comunicação |
| GET | `/api/v1/stations/{station_id}/latest` | Público | Leitura anônima | Obter a última observação recebida |
| GET | `/api/v1/stations/{station_id}/observations` | Público | Leitura anônima | Paginar medições por período |
| GET | `/api/v1/stations/{station_id}/summary` | Público | Leitura anônima | Calcular estatísticas de um período |
| GET | `/api/v1/stations/{station_id}/export.csv` | Público | Leitura anônima | Baixar medições em CSV |
| GET | `/data/report/` | Ingestão | Rede autorizada | Receber uma transmissão da WS-2000 |
| GET | `/data/report` | Ingestão | Rede autorizada | Receber a mesma transmissão sem barra final |
| GET | `/health` | Ingestão | Operação local | Verificar o processo |
| GET | `/ready` | Ingestão | Operação local | Verificar acesso às tabelas |
| GET | `/monitor/stations` | Ingestão | Operação local | Acompanhar as estações |
| GET | `/docs` | DEV | Loopback | Abrir o Swagger UI |
| GET, HEAD | `/openapi.json` | DEV | Loopback | Ler a especificação do processo combinado |
| GET, HEAD | `/docs-assets/{path}` | DEV | Loopback | Servir arquivos estáticos do Swagger |

A tabela conta cada caminho uma vez, inclusive o alias do console e a montagem de arquivos estáticos. O processo combinado DEV registra os 14 caminhos. O leitor isolado registra seis e a ingestão isolada registra cinco. Os três restantes existem apenas em DEV. As diferenças de resposta nos caminhos compartilhados estão detalhadas abaixo.

A estação Ambient Weather WS-2000 (ou o simulador em DEV) envia o protocolo `Same As AMBWeather` ao processo `ingest`. Esse processo valida a transmissão e grava os dois horários e os sensores em SQLite. O processo `public` abre o mesmo arquivo para leitura. A coleta continua mesmo com o dashboard fechado ou o túnel indisponível.

| Ambiente | Endereço padrão | Uso |
|---|---|---|
| DEV · leitor | `http://127.0.0.1:8080/api/v1` | Contrato do dashboard, inclusive os limites de produção |
| DEV · ingestão | `http://127.0.0.1:8001` | Console, simulador e monitoramento local |
| DEV · combinado | `http://127.0.0.1:8000` | Swagger, diagnóstico e cadastro interno das estações |
| SESC · futuro | `/api/v1` na origem HTTPS do dashboard | A TI definirá o domínio. O túnel encaminhará a API ao leitor local |

Os caminhos HTTP dos exemplos partem da raiz do respectivo serviço. Os IDs, horários, medições, arquivos e respostas de exemplo são ilustrativos. Descubra o ID pelo endpoint de estações.

## Como ler os contratos

Em **cada rota** desta referência, corpo da requisição, cabeçalhos obrigatórios e credenciais de usuário: **Não se aplica**. O acesso depende do serviço indicado. Parâmetros de caminho ou de query ausentes da descrição: **Não se aplica**. Todos os parâmetros de caminho são obrigatórios e sem valor padrão. O sucesso de um GET é `200`, normalmente com `application/json`. CSV, confirmação do console, HTML e arquivos estáticos têm o formato indicado em suas rotas.

| Parâmetro | Onde usar | Tipo, padrão e validação |
|---|---|---|
| `station_id` | Todos os caminhos que contêm `{station_id}` | Inteiro entre 1 e 9223372036854775807. No navegador use IDs retornados pelo servidor. O tipo `number` só representa inteiros com exatidão até `Number.MAX_SAFE_INTEGER`. |
| `page` | Lista pública, monitor e histórico | Inteiro opcional, começa em 1 (padrão). Na lista e no monitor o máximo é 1.000.000. No histórico, `(page - 1) × page_size` precisa caber em inteiro assinado de 64 bits. |
| `page_size` | Mesmas rotas de `page` | Inteiro opcional de 1 a `MAX_PAGE_SIZE` (padrão configurado 500). Omitido, vale o menor entre 100 e esse teto. |
| `start`, `end` | Histórico, resumo e CSV | Opcionais. Envie strings ISO 8601 com fuso, por exemplo `2026-11-20T00:00:00Z`. Os limites incluem os dois extremos e filtram `measured_at_utc`. Podem ser iguais. Use `URLSearchParams` para codificar offsets com `+`. |
| `order` | Somente histórico | String opcional `asc` (padrão) ou `desc`, por instante da medição. |

No leitor público, sem datas o período é o **dia corrente UTC** inteiro. Com uma única data, o servidor calcula o outro extremo somando ou subtraindo `MAX_PERIOD_DAYS` (padrão 31 dias). Com ambas, o início precisa ser anterior ou igual ao fim e a duração deve ficar dentro desse limite. Para exibir um dia civil de Recife, envie os limites daquele dia com seu fuso, inclusive na exportação.

## Padrão de unidades meteorológicas

O receptor converte as unidades originais da WS-2000 na ingestão. O SQLite guarda as grandezas normalizadas e conserva os parâmetros originais apenas em `raw_payload` para diagnóstico interno. JSON e CSV públicos já contêm os valores métricos. Use o valor recebido e arredonde apenas na apresentação.

| Propriedades de uma observação | Grandeza, na ordem indicada | Unidade |
|---|---|---|
| `outdoor_temperature_c`, `indoor_temperature_c` | Temperatura externa e interna | °C |
| `outdoor_humidity_pct`, `indoor_humidity_pct` | Umidade relativa externa e interna | % |
| `wind_speed_ms`, `wind_gust_ms` | Velocidade do vento e rajada | m/s |
| `wind_direction_deg`, `wind_gust_direction_deg` | Direção do vento e da rajada | graus (°) |
| `daily_rain_mm`, `hourly_rain_mm`, `weekly_rain_mm`, `monthly_rain_mm`, `yearly_rain_mm` | Acumulados do dia, hora, semana, mês e ano | mm |
| `absolute_pressure_hpa`, `relative_pressure_hpa` | Pressão absoluta e relativa | hPa |
| `uv_index` | Índice ultravioleta | adimensional |
| `solar_radiation_wm2` | Radiação solar | W/m² |

Os 17 sensores são números JSON ou `null`. O OpenAPI permite omitir cada sensor e o modelo usa `null` por padrão. A serialização atual inclui as chaves dos sensores ausentes com `null`. Na interface, use `valor == null` para mostrar “sem leitura”. Zero é uma medida válida. Para chuva, conserve o intervalo do acumulador e evite somar valores sucessivos do mesmo período.

## Consultas públicas, rota por rota

Os exemplos desta seção usam o leitor na porta 8080. Todas as seis rotas compartilham os erros de infraestrutura `414`, `429`, `503` e `500` descritos em **Respostas de erro**. Nas rotas com ID também se aplicam `404` para estação desconhecida e `422` para ID inválido.

### GET `/api/v1/stations`

Lista de `PublicStation` em ordem crescente de ID. Query opcional: `page` e `page_size`. A resposta é um array simples, inclusive quando só há uma estação. Uma página após a última ou um banco sem estações devolve `[]`. Paginação inválida resulta em `422`. Use esta chamada para preencher o seletor de estações.

```http
GET /api/v1/stations?page=2&page_size=100
```

```json
[]
```

### GET `/api/v1/stations/{station_id}`

Devolve um objeto `PublicStation`. Query: Não se aplica. Atualize esta consulta para saber se a estação ainda transmite. Exemplo de `GET /api/v1/stations/1`:

```json
{
  "id": 1, "name": "Simulador WS-2000", "model": "WS-2000", "is_simulated": true,
  "last_seen_at": "2026-11-20T14:30:02Z", "communication": "online", "seconds_since_contact": 58,
  "last_measured_at_utc": "2026-11-20T14:30:00Z", "seconds_since_measurement": 60
}
```

Todos os campos são obrigatórios. `id` é o inteiro da estação. `name` e `model` são textos. `is_simulated` identifica a origem simulada. `last_seen_at` é a data UTC da última transmissão aceita, inclusive repetida. `seconds_since_contact` é a idade inteira desse contato, com mínimo zero. `communication` é `online` abaixo de `STATION_DELAY_SECONDS` (180 s), `delayed` a partir desse limite e `offline` a partir de `STATION_TIMEOUT_SECONDS` (600 s). Os limiares são configuráveis.

`last_measured_at_utc` é o maior instante de medição conhecido. `seconds_since_measurement` é sua idade em segundos inteiros e pode ser negativa se o relógio do console estiver adiantado. Esses dois campos são nulos quando a estação ainda não tem observações. Um reenvio pode manter a estação online mesmo que a medição exibida seja antiga.

### GET `/api/v1/stations/{station_id}/latest`

Devolve `ObservationOut`, a observação recebida mais recentemente, com desempate pelo maior `id`. Uma transmissão atrasada pode ocupar essa posição. Query: Não se aplica. Para uma estação cadastrada sem observações, devolve `404` com `Estação sem observações`. Exemplo de `GET /api/v1/stations/1/latest`:

```json
{
  "id": 1, "station_id": 1,
  "measured_at_utc": "2026-11-20T14:30:00Z", "received_at_utc": "2026-11-20T14:30:02Z",
  "outdoor_temperature_c": 30.0, "indoor_temperature_c": null,
  "outdoor_humidity_pct": 60.0, "indoor_humidity_pct": null,
  "wind_speed_ms": 5.36448, "wind_gust_ms": null,
  "wind_direction_deg": null, "wind_gust_direction_deg": null,
  "daily_rain_mm": 2.54, "hourly_rain_mm": null, "weekly_rain_mm": null,
  "monthly_rain_mm": null, "yearly_rain_mm": null,
  "absolute_pressure_hpa": null, "relative_pressure_hpa": null,
  "uv_index": null, "solar_radiation_wm2": null
}
```

As quatro propriedades obrigatórias no schema são `id` (inteiro da observação), `station_id` (inteiro da estação), `measured_at_utc` (hora do console) e `received_at_utc` (primeira recepção daquela observação no servidor). Os dois horários são strings ISO 8601 em UTC. A tabela de unidades descreve cada sensor. Use o instante da medição nos cartões meteorológicos.

### GET `/api/v1/stations/{station_id}/observations`

Histórico paginado. Query opcional: `start`, `end`, `page`, `page_size` e `order`. O objeto `History` exige `page` (inteiro solicitado), `page_size` (inteiro efetivo) e `items` (array de objetos `ObservationOut` completos, como no exemplo de `latest`). Não há total nem cursor. Período ou paginação inválidos recebem `422`. Exemplo de página vazia para estação existente:

```http
GET /api/v1/stations/1/observations?start=2026-11-20T00:00:00Z&end=2026-11-20T23:59:59.999999Z&page=2&page_size=50&order=asc
```

```json
{"page":2,"page_size":50,"items":[]}
```

Leia mais uma página enquanto `items.length === page_size`. Uma última página cheia exige uma consulta adicional para descobrir o fim. Fixe `start` e `end` entre páginas. A paginação por deslocamento pode mudar se chegarem leituras atrasadas para o período. Use `id` para identificar pontos no gráfico.

### GET `/api/v1/stations/{station_id}/summary`

Query opcional: `start` e `end`. Devolve `Summary` agregado de todo o período. Todas as chaves são obrigatórias. `sample_count` é o número inteiro de observações, incluindo amostras com sensores nulos. Os trios `temperature_min_c`, `temperature_avg_c`, `temperature_max_c` e `humidity_min_pct`, `humidity_avg_pct`, `humidity_max_pct` trazem mínima, média e máxima externas em °C e %. `wind_avg_ms` e `wind_max_ms` usam a velocidade do vento em m/s. Cada estatística é um número ou `null` quando o sensor está ausente em todo o período. A média usa as amostras com valor. `latest` é um objeto `ObservationOut` completo com o recebimento mais recente dentre as medições do período, ou `null`. Período inválido recebe `422`. Use esta chamada para os indicadores do período, inclusive quando o histórico tiver várias páginas.

```http
GET /api/v1/stations/1/summary?start=2026-11-19T00:00:00Z&end=2026-11-19T23:59:59.999999Z
```

```json
{
  "sample_count": 0, "temperature_min_c": null, "temperature_avg_c": null, "temperature_max_c": null,
  "humidity_min_pct": null, "humidity_avg_pct": null, "humidity_max_pct": null,
  "wind_avg_ms": null, "wind_max_ms": null, "latest": null
}
```

### GET `/api/v1/stations/{station_id}/export.csv`

Query opcional: `start` e `end`. O leitor aceita até `MAX_CSV_ROWS` observações (padrão 5.000), além do limite de duração. Ultrapassar qualquer limite recebe `422`. O arquivo contém todas as observações do período em ordem crescente de medição. JSON de sucesso: **Não se aplica**. O navegador pode salvar o corpo `text/csv; charset=utf-8` com o nome de `Content-Disposition: attachment; filename="estacao-1.csv"`, onde `1` é o ID pedido. O arquivo usa vírgula, ponto decimal, quebras CRLF, UTF-8 sem BOM e células vazias para sensores nulos. Os horários são ISO 8601 com offset UTC. Estação existente e período vazio produzem `200` apenas com a primeira linha.

```http
GET /api/v1/stations/1/export.csv?start=2026-11-20T14:30:00Z&end=2026-11-20T14:30:00Z
```

```csv
Estação (ID),Medição (UTC),Recebimento (UTC),Temperatura externa (°C),Temperatura interna (°C),Umidade externa (%),Umidade interna (%),Velocidade do vento (m/s),Rajada (m/s),Direção do vento (°),Direção da rajada (°),Chuva acumulada diária (mm),Chuva acumulada horária (mm),Chuva acumulada semanal (mm),Chuva acumulada mensal (mm),Chuva acumulada anual (mm),Pressão absoluta (hPa),Pressão relativa (hPa),Índice UV (adimensional),Radiação solar (W/m²)
1,2026-11-20T14:30:00+00:00,2026-11-20T14:30:02+00:00,30.0,,60.0,,5.36448,,,,2.54,,,,,,,,
```

## Ingestão e diagnóstico local

Estas rotas pertencem ao processo `ingest` (porta 8001). O IP da conexão deve pertencer a `INGEST_NETWORKS` em todas elas, inclusive nas sondas. A ingestão descarta cabeçalhos de proxy. Uma origem recusada recebe `403 {"detail":"Origem fora das redes de ingestão"}`. No processo combinado `dev` o receptor mantém a mesma verificação e as três rotas de diagnóstico ficam disponíveis em loopback. Uso pelo React público em cada rota desta seção: **Não se aplica**.

### GET `/data/report/` e GET `/data/report`

Os dois caminhos executam a mesma ingestão sem redirecionamento. O console envia HTTP GET com os parâmetros codificados na URL em UTF-8. Parâmetros de caminho: Não se aplica. Corpo: Não se aplica. Envie a requisição sem `Transfer-Encoding` e com `Content-Length` ausente ou `0`.

| Query | Tipo e presença | Validação e significado |
|---|---|---|
| `MAC` | Texto obrigatório | 12 dígitos hexadecimais, juntos ou em seis pares com o mesmo separador (`:` ou `-`). Identifica a estação. |
| `dateutc` | Texto obrigatório | Data e hora UTC do console no formato `YYYY-MM-DD HH:MM:SS`. |
| `dev_simulated` | Texto opcional | Quando presente deve valer `1` e requer `ALLOW_SIMULATED=true`. Ausente identifica transmissão física. |
| `tempf`, `tempinf` | Números opcionais | Temperaturas externa e interna. Aceitam negativos. |
| `humidity`, `humidityin` | Números opcionais | Umidades externa e interna entre 0 e 100 inclusive. |
| `winddir`, `windgustdir` | Números opcionais | Direções em graus de 0 a 360 inclusive. |
| `windspeedmph`, `windgustmph` | Números opcionais | Velocidade e rajada, mínimo zero. |
| `dailyrainin`, `hourlyrainin`, `weeklyrainin`, `monthlyrainin`, `yearlyrainin` | Números opcionais | Acumuladores de chuva, mínimo zero. |
| `baromabsin`, `baromrelin` | Números opcionais | Pressões absoluta e relativa, mínimo zero. |
| `uv`, `solarradiation` | Números opcionais | Índice UV e radiação solar, mínimo zero. |

Nenhum sensor possui valor numérico padrão. Cada pacote exige ao menos um campo de sensor conhecido ou um parâmetro desconhecido além dos identificadores. Campos conhecidos repetidos, resultados não finitos e valores fora da faixa são inválidos. Campos desconhecidos, inclusive repetidos, são preservados no payload interno. As unidades de entrada e as conversões constam em **Protocolo e regras de armazenamento**.

Exemplos independentes dos dois caminhos em DEV, com MAC fictício e simulação habilitada:

```http
GET /data/report/?MAC=020000002000&dateutc=2026-11-20+14%3A30%3A00&tempf=86&dev_simulated=1
```

```http
GET /data/report?MAC=020000002000&dateutc=2026-11-20+14%3A30%3A00&tempf=86&dev_simulated=1
```

Resposta de **cada** exemplo após commit, também no reenvio do mesmo instante:

```http
HTTP/1.1 200 OK
Content-Type: text/plain; charset=utf-8
Cache-Control: no-store

OK
```

O texto é configurável em `ACK_TEXT`. JSON de sucesso: Não se aplica. A chave única de estação e instante conserva a primeira medição. A retransmissão atualiza o último contato. Erros têm a forma `{"detail":"mensagem"}`:

| HTTP | Exemplo de `detail` | Condição |
|---|---|---|
| 403 | `Origem fora das redes de ingestão` | IP fora da lista permitida |
| 409 | `MAC já cadastrado com outra origem` | O mesmo identificador alternou entre simulação e equipamento físico |
| 413 | `Excesso de parâmetros` ou `Envie os parâmetros na query de GET` | Mais de `MAX_PARAMETERS` (128 por padrão) ou corpo sinalizado |
| 414 | `Query excede o limite` | Query acima de `MAX_QUERY_BYTES` (8192 por padrão) |
| 422 | `MAC inválido`, `dateutc inválido ou ausente`, `Transmissão sem parâmetros de sensores`, `Simulação desabilitada nesta instância` | Identificação, codificação, simulação ou valor inválido. A mensagem indica a rejeição e pode nomear um campo conhecido. |
| 503 | `Banco de dados indisponível` | Erro de persistência |

### GET `/health`

Sonda do processo. Caminho parametrizado e query: Não se aplica. `GET /health` → `200 {"status":"ok"}`. A única chave obrigatória, `status`, é texto com valor `ok`. Responde também com banco vazio ou indisponível. Erro de acesso: `403` na ingestão.

### GET `/ready`

Testa acesso às tabelas `stations` e `observations`. Caminho parametrizado e query: Não se aplica. `GET /ready` → `200 {"status":"ready"}` com a única chave obrigatória `status`, texto com valor `ready`. Uma base migrada vazia está pronta. Falha de banco devolve `503 {"detail":"Banco de dados indisponível"}`. Erro de acesso: `403` na ingestão.

### GET `/monitor/stations`

Consulta o estado atual de comunicação. Caminho parametrizado: Não se aplica. Usa a mesma query `page`, `page_size` e a mesma resposta `PublicStation[]` da lista pública, com ID crescente e `[]` para página vazia. Exemplo: `GET /monitor/stations?page=1&page_size=1`.

```json
[{
  "id": 1, "name": "Simulador WS-2000", "model": "WS-2000", "is_simulated": true,
  "last_seen_at": "2026-11-20T14:30:02Z", "communication": "online", "seconds_since_contact": 58,
  "last_measured_at_utc": "2026-11-20T14:30:00Z", "seconds_since_measurement": 60
}]
```

Erros: `403` para acesso recusado, `422` para paginação e `503` para falha de banco. O detalhe de validação segue o formato local descrito em **Respostas de erro**.

## Diferenças no processo combinado de desenvolvimento

Na porta 8000, `GET /api/v1/stations` lista **todas** as estações por ID, sem parâmetros de consulta. Responde `200` com um array de `StationOut` ou `[]`. `GET /api/v1/stations/{station_id}` usa o mesmo intervalo de ID do leitor e devolve um único `StationOut`. Exemplo da resposta de `GET /api/v1/stations/1`:

```json
{
  "id": 1, "mac_address": "02:00:00:00:20:00", "name": "Simulador WS-2000",
  "model": "WS-2000", "is_simulated": true,
  "created_at": "2026-11-20T14:30:02Z", "updated_at": "2026-11-20T14:30:02Z",
  "last_seen_at": "2026-11-20T14:30:02Z"
}
```

Todas essas chaves são obrigatórias e têm valor não nulo. `mac_address` é texto com o MAC normalizado. `created_at` e `updated_at` são strings ISO 8601 UTC de cadastro e atualização. Os demais campos seguem o significado da estação pública. Exemplo de lista antes do primeiro envio: `GET /api/v1/stations` → `200 []`. A lista e o detalhe podem devolver `503`. Para o detalhe também valem `404` (estação desconhecida) e `422` (ID inválido).

No histórico, resumo e CSV da porta 8000, datas omitidas deixam o respectivo extremo aberto. A validação de ordem e o teto de página do histórico continuam ativos. O CSV local é enviado em lotes de 256 observações, sem o teto de linhas do leitor. O cache e as cotas públicas aplicam-se ao processo `public`. Exercite o dashboard contra esse processo mesmo durante o desenvolvimento.

## Swagger, OpenAPI e arquivos locais

Estas três rotas existem apenas no serviço combinado em loopback. Autenticação de usuário, query e integração direta pelo dashboard: **Não se aplica**. Para `HEAD`, o servidor envia os cabeçalhos sem o corpo. ReDoc não está registrado.

| Requisição de exemplo | Resposta de exemplo | Contrato |
|---|---|---|
| `GET /docs` | `200 text/html` com `<title>API meteorológica WS-2000</title>` (trecho) | Swagger UI carrega seu JS, CSS e ícone locais e consulta `/openapi.json`. Parâmetros de caminho e JSON de sucesso: Não se aplica. |
| `GET /openapi.json` ou `HEAD /openapi.json` | `200 application/json`. Trecho do GET: `{"openapi":"3.1.0","info":{"title":"API meteorológica WS-2000","version":"0.2.0"}}` | Sem parâmetro de caminho. O documento completo contém `openapi` (versão, string), `info` (objeto com título e versão), `paths` (objeto de caminhos, métodos, parâmetros e respostas) e `components.schemas` (modelos por nome). Seu conteúdo independe de haver estações cadastradas. |
| `GET /docs-assets/favicon-32x32.png` ou `HEAD /docs-assets/swagger-ui.css` | `200`. O GET inicia com os bytes PNG `89 50 4E 47 0D 0A 1A 0A`; o HEAD retorna tipo CSS e corpo vazio. | Montagem estática `/docs-assets/{path}`. `path` é o nome relativo obrigatório do recurso, podendo conter subdiretórios. Resposta binária ou textual conforme arquivo. JSON de sucesso: Não se aplica. Arquivo ausente: `404 {"detail":"Not Found"}`. |

As rotas locais aplicam as respostas do framework para método incompatível (`405`). Para arquivos estáticos, pedidos condicionais podem retornar `304` e pedidos com `Range` podem receber `206` ou `416`. Esses códigos pertencem ao servidor de arquivos.

### O que o OpenAPI descreve

Na porta 8000, abra `http://127.0.0.1:8000/docs` ou `http://127.0.0.1:8000/openapi.json`. A especificação combinada contém dez caminhos GET com as tags `Serviço`, `Console`, `Monitoramento interno`, `Estações` e `Observações`. O alias sem barra, o Swagger, o próprio JSON e a montagem estática ficam fora de `paths`. O leitor tem seis caminhos GET nas tags `Estações públicas` e `Observações`. A ingestão tem quatro caminhos no schema e um alias adicional. `OPTIONS` de preflight CORS é tratado por middleware e não soma uma rota. Uma variante com barra diferente pode receber redirecionamento `307` se só o outro caminho estiver registrado.

Para obter a especificação exata do leitor sem abrir uma rota de documentação, execute com o Python da `.venv` na raiz:

```bash
python -c "import json; from app.main import create_public_app; print(json.dumps(create_public_app().openapi(), indent=2, ensure_ascii=False))"
```

O schema público declara os parâmetros de ID e query, os modelos de sucesso, o CSV e `x-unit` nas grandezas. Algumas descrições de operação são apenas os nomes gerados pelo FastAPI. Os limites definidos pelo `.env`, os valores efetivos para parâmetros omitidos, cabeçalhos, ordenação de `latest` e estados vazios exigem a leitura das regras do serviço. O OpenAPI combinado não declara a query do console (o parser lê a URL bruta), os schemas das sondas são genéricos e as rotas locais não enumeram todos os erros. O leitor declara `404/422/429/503` em bloco para todas as operações e omite `414/500`. O contrato de erro de validação também varia entre o leitor e o Swagger combinado.

# Segurança e limites de acesso

O dashboard usa as seis operações GET da tabela pública. Todas permitem leitura anônima. Nenhuma exige login, cookie, token ou chave de API. Na futura implantação, apenas o leitor deve receber tráfego do túnel. Ele não registra `/data/report/`, o alias sem barra, as sondas internas, a documentação ou operações administrativas. O navegador nunca deve chamar a ingestão. O cadastro local com MAC, o payload bruto, os IPs e os dados de operação ficam fora da interface pública.

Em DEV, o modelo de `CORS_ORIGINS` autoriza `http://localhost:5173`. A origem do Vite precisa coincidir exatamente, inclusive protocolo e porta. O leitor e o processo combinado permitem o método GET no preflight e expõem `Content-Disposition` e `Retry-After` ao JavaScript. O navegador envia `Origin` quando necessário. A ingestão não instala CORS. Na futura produção de mesma origem, a configuração exemplificada é `[]`. Para um dashboard em outra origem, a TI deve cadastrá-la explicitamente. CORS rege a leitura pelo navegador. A proteção da ingestão depende da separação das aplicações e do IP da conexão.

A cota do leitor opera em janelas fixas de um minuto por processo, com padrões de 120 requisições por cliente e 1.200 no total. Consultas que acertam o cache também consomem cota. O IP observado depende da configuração do proxy confiável. Visitantes podem compartilhar a mesma cota quando o proxy mascara sua origem. A configuração de execução usa um worker. Uma query inteira acima de `MAX_QUERY_BYTES` (8.192 bytes por padrão) é rejeitada antes de consultar o banco.

## Respostas de erro

No leitor, erros da aplicação usam `application/json` com uma única propriedade obrigatória `detail` do tipo string. Exemplo: `{"detail":"Estação desconhecida"}`. A tabela indica quais erros podem ocorrer em cada operação. Respostas de rede e do proxy podem ter outro formato.

| HTTP e `detail` do leitor | Quando ocorre | Tratamento no dashboard |
|---|---|---|
| 404 · `Estação desconhecida` | O ID é válido, mas a estação não existe | Atualizar a lista e permitir nova seleção |
| 404 · `Estação sem observações` | `latest` de uma estação cadastrada sem medições | Mostrar “aguardando primeira medição” |
| 422 · `Parâmetros de consulta inválidos` | Falha de tipo, faixa declarada, fuso ausente ou enum inválido (também em parâmetro de caminho) | Corrigir a entrada e preservar os filtros para edição |
| 422 · `start deve anteceder end`, `Reduza o período consultado` ou `Instante fora do intervalo suportado` | Ordem, duração ou cálculo dos limites UTC inválido | Ajustar as datas antes de repetir |
| 422 · `Página excede o limite` ou `Paginação excede o limite` | Tamanho acima do teto na lista ou no histórico, ou deslocamento excessivo no histórico | Reduzir o tamanho ou ajustar a página |
| 422 · `Reduza o período para exportar menos linhas` | O período do CSV contém registros demais | Dividir a exportação em intervalos menores |
| 414 · `Query excede o limite` | URL com query acima do limite | Enviar apenas os filtros necessários |
| 429 · `Limite de requisições atingido` | Cota por cliente ou cota total atingida | Ler `Retry-After` (atualmente `60` segundos) e reagendar |
| 503 · `Banco de dados indisponível` | Falha do SQLAlchemy ao acessar o banco | Manter o último valor com sua hora e tentar depois |
| 500 · `Falha interna no serviço` | Exceção inesperada no leitor | Mostrar indisponibilidade, espaçar tentativas e registrar recorrência |
| 404 · `Not Found` / 405 · `Method Not Allowed` | Caminho ausente / método incompatível | Verificar a base URL, a rota e o método |

No ambiente combinado, uma falha de validação declarativa devolve `422` com `detail` como **array**, por exemplo `{"detail":[{"type":"int_parsing","loc":["path","station_id"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"abc"}]}`. Cada item tem `type` e `msg` (texto), `loc` (lista de nomes ou índices) e pode incluir `input` e `ctx`. Já os limites validados pelo próprio código produzem `detail` textual, inclusive em DEV. As falhas de SQLAlchemy recebem `503` em todos os serviços. O tratamento genérico JSON de `500` é específico do leitor. Restrição de origem da ingestão gera `403`. Para requisições públicas, autenticação e `401`: **Não se aplica**.

Um preflight OPTIONS com origem, método ou cabeçalhos rejeitados pode receber `400` em texto do middleware. O navegador também pode impedir a leitura de uma resposta sem permissão CORS. Se `fetch` rejeitar sem `Response`, trate como falha de conexão ou de origem, separadamente de um erro JSON lido da API.

# Guia de integração com React + TypeScript

Use o mesmo contrato em DEV e PROD. Em DEV, inicie `python -m app.serve ingest` e `python -m app.serve public` com a `.venv` ativa em terminais separados. Com o perfil DEV instalado, `python scripts/simulate_station.py --samples 2 --interval 2` fornece dados sem equipamento físico. Aponte o Vite para o **leitor**, na porta 8080 por padrão.

### Tipos de resposta

Estes tipos descrevem o JSON efetivamente emitido. Datas permanecem strings durante o transporte. As propriedades de sensores aceitam `?` para também respeitar o schema OpenAPI, que admite sua omissão.

```ts
type UTCString = string

interface PublicStation {
  id: number
  name: string
  model: string
  is_simulated: boolean
  last_seen_at: UTCString
  communication: "online" | "delayed" | "offline"
  seconds_since_contact: number
  last_measured_at_utc: UTCString | null
  seconds_since_measurement: number | null
}

interface ObservationOut {
  id: number
  station_id: number
  measured_at_utc: UTCString
  received_at_utc: UTCString
  outdoor_temperature_c?: number | null
  indoor_temperature_c?: number | null
  outdoor_humidity_pct?: number | null
  indoor_humidity_pct?: number | null
  wind_speed_ms?: number | null
  wind_gust_ms?: number | null
  wind_direction_deg?: number | null
  wind_gust_direction_deg?: number | null
  daily_rain_mm?: number | null
  hourly_rain_mm?: number | null
  weekly_rain_mm?: number | null
  monthly_rain_mm?: number | null
  yearly_rain_mm?: number | null
  absolute_pressure_hpa?: number | null
  relative_pressure_hpa?: number | null
  uv_index?: number | null
  solar_radiation_wm2?: number | null
}

interface ObservationPage {
  page: number
  page_size: number
  items: ObservationOut[]
}

interface Summary {
  sample_count: number
  temperature_min_c: number | null
  temperature_avg_c: number | null
  temperature_max_c: number | null
  humidity_min_pct: number | null
  humidity_avg_pct: number | null
  humidity_max_pct: number | null
  wind_avg_ms: number | null
  wind_max_ms: number | null
  latest: ObservationOut | null
}

interface PublicError { detail: string }
```

### Base URL, HTTP e filtros

No `.env.local` do **futuro frontend** pode-se definir `VITE_API_BASE_URL=http://127.0.0.1:8080/api/v1`. Em produção na mesma origem, use `/api/v1`. Se a TI escolher outra origem, use a URL HTTPS completa e configure o CORS no backend. Variáveis `VITE_*` são públicas. Os blocos TypeScript desta seção podem ser usados juntos em um módulo do cliente.

```ts
const base = (import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "http://127.0.0.1:8080/api/v1" : "/api/v1")).replace(/\/$/, "")

class ApiHttpError extends Error {
  readonly status: number
  readonly retryAfter: number | null

  constructor(status: number, message: string, retryAfter: number | null) {
    super(message)
    this.status = status
    this.retryAfter = retryAfter
  }
}

async function request(path: string, signal?: AbortSignal): Promise<Response> {
  const response = await fetch(base + path, { signal })
  if (response.ok) return response
  const body = await response.json().catch(() => null)
  const retry = response.headers.get("Retry-After")
  throw new ApiHttpError(response.status,
    typeof body?.detail === "string" ? body.detail : "Falha HTTP " + response.status,
    retry !== null && /^\d+$/.test(retry) ? Number(retry) : null)
}

async function json<T>(path: string, signal?: AbortSignal): Promise<T> {
  return (await request(path, signal)).json() as Promise<T>
}

const stations = (page = 1, pageSize = 50, signal?: AbortSignal) =>
  json<PublicStation[]>("/stations?" + new URLSearchParams({
    page: String(page), page_size: String(pageSize)
  }), signal)
const station = (id: number, signal?: AbortSignal) =>
  json<PublicStation>("/stations/" + id, signal)
const latest = (id: number, signal?: AbortSignal) =>
  json<ObservationOut>("/stations/" + id + "/latest", signal)

interface Period { start?: string; end?: string }
function dates(period: Period): URLSearchParams {
  const query = new URLSearchParams()
  if (period.start) query.set("start", period.start)
  if (period.end) query.set("end", period.end)
  return query
}

function historyPage(id: number, period: Period, page = 1, pageSize = 50,
                     order: "asc" | "desc" = "asc", signal?: AbortSignal) {
  const query = dates(period)
  query.set("page", String(page))
  query.set("page_size", String(pageSize))
  query.set("order", order)
  return json<ObservationPage>("/stations/" + id + "/observations?" + query, signal)
}

const summary = (id: number, period: Period, signal?: AbortSignal) =>
  json<Summary>("/stations/" + id + "/summary?" + dates(period), signal)
```

Exemplo de leitura de um dia de Recife. No React, passe um `AbortSignal` e cancele requisições ao trocar de estação ou desmontar o componente. O exemplo busca apenas a primeira página. A interface pode usar `nextPage` quando o usuário pedir mais dados.

```ts
async function loadDay(signal: AbortSignal) {
  const available = await stations(1, 50, signal)
  if (available.length === 0) return { available }
  const id = available[0].id
  const day = { start: "2026-11-20T00:00:00-03:00", end: "2026-11-20T23:59:59.999999-03:00" }
  const [status, totals, readings] = await Promise.all([
    station(id, signal), summary(id, day, signal), historyPage(id, day, 1, 50, "asc", signal)
  ])
  const last = await latest(id, signal).catch((error: unknown) => {
    if (error instanceof ApiHttpError && error.status === 404 &&
        error.message === "Estação sem observações") return null
    throw error
  })
  const nextPage = readings.items.length === readings.page_size ? readings.page + 1 : null
  return { available, status, totals, readings, last, nextPage }
}
```

### Download pelo navegador

Dispare o download a partir de uma ação do usuário. O exemplo usa o nome declarado pelo servidor e um nome alternativo baseado no ID. O mesmo tratamento de `422` ou `429` ocorre antes de criar o arquivo.

```ts
async function downloadCsv(id: number, period: Period, signal?: AbortSignal) {
  const response = await request("/stations/" + id + "/export.csv?" + dates(period), signal)
  const blobUrl = URL.createObjectURL(await response.blob())
  const link = document.createElement("a")
  const disposition = response.headers.get("Content-Disposition") ?? ""
  link.download = /filename="(estacao-\d+\.csv)"/.exec(disposition)?.[1] ?? "estacao-" + id + ".csv"
  link.href = blobUrl
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
}
```

### Atualização, cache e horário de apresentação

Para uma estação que transmite a cada 60 segundos, comece consultando o detalhe e `latest` uma vez por minuto. Atualize resumo e histórico quando mudarem a estação ou os filtros. Em uma visão diária contínua, atualize o resumo a cada cinco minutos. Pause as consultas de abas ocultas e compartilhe a resposta entre componentes que exibem a mesma estação.

O cache do leitor é em memória, por processo, com até 32 entradas. Os TTLs padrão são 60 s para `latest` (`CACHE_TTL_SECONDS`), 60 s para histórico (`HISTORY_CACHE_TTL_SECONDS`) e 300 s para resumo (`SUMMARY_CACHE_TTL_SECONDS`). Zero desativa o respectivo cache. A chave inclui a versão baseada no maior ID de observação do banco. Uma nova inserção, mesmo de medição antiga, muda a versão. Lista, detalhe, monitor, CSV e ingestão ficam fora do cache. O middleware público marca as respostas processadas com `Cache-Control: no-store`.

Agende a próxima busca depois que a atual terminar. Em `429`, respeite `Retry-After`. Em `503`, `500` ou falha de rede, mantenha a última medição visível com seu horário, sinalize a falha de atualização e aumente o intervalo entre tentativas (por exemplo, 1, 2 e 4 minutos com pequena variação aleatória). Retome o intervalo habitual após sucesso. Uma falha ao buscar a API, por si só, não determina o estado `offline` da estação.

Use `communication` para mostrar o contato com a estação e `measured_at_utc` da leitura apresentada para indicar a idade daquele dado. `last_measured_at_utc` pode ser mais recente que a medição retornada por `latest`. Para mostrar hora local com a data correta:

```ts
const recife = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Recife", dateStyle: "short", timeStyle: "medium"
})
// recife.format(new Date(observacao.measured_at_utc))
```

## Funcionalidades previstas, mas ainda não implementadas

- O dashboard React + TypeScript + Vite será desenvolvido a partir das consultas acima. A atualização disponível hoje é por HTTP periódico. O backend não oferece WebSocket, SSE nem endpoint de totais de páginas.
- A instalação física, a confirmação do intervalo de envio do console, a escolha do domínio/origem e a publicação do túnel dependem da TI do SESC. Serviços, backup e modelos de configuração já existem no repositório. Para desenvolver o cliente, bastam o simulador e o leitor locais.

<a id="armazenamento"></a>

## Protocolo e regras de armazenamento

O receptor aceita GET em `/data/report/` e `/data/report`, sem redirecionamento. O MAC normalizado identifica a estação. `dateutc` segue `YYYY-MM-DD HH:MM:SS` e representa UTC. O corpo de confirmação do firmware não aparece definido nas referências consultadas. A implementação envia texto simples configurável após o commit, inclusive para duplicatas. O modo implementado é o upload HTTP com parâmetros legíveis na query. [Documentação oficial, seção Awnet Advanced Settings](https://ambientweather.com/support/aw-misc/)

| Entrada | Colunas normalizadas | Conversão |
|---|---|---|
| tempf, tempinf | outdoor_temperature_c, indoor_temperature_c | (°F − 32) × 5 / 9 |
| humidity, humidityin | outdoor_humidity_pct, indoor_humidity_pct | % (0–100) |
| windspeedmph, windgustmph | wind_speed_ms, wind_gust_ms | mph × 0,44704 |
| winddir, windgustdir | wind_direction_deg, wind_gust_direction_deg | graus (0–360) |
| dailyrainin, hourlyrainin, weeklyrainin, monthlyrainin, yearlyrainin | daily_rain_mm, hourly_rain_mm, weekly_rain_mm, monthly_rain_mm, yearly_rain_mm | polegadas × 25,4 |
| baromabsin, baromrelin | absolute_pressure_hpa, relative_pressure_hpa | inHg × 33,8638866667 |
| uv, solarradiation | uv_index, solar_radiation_wm2 | índice UV e W/m² |

| Regra | Comportamento |
| --- | --- |
| **Chuva acumulada** | Cada acumulador conserva seu intervalo. Por exemplo, se o acumulado diário aparece como 5 mm em três leituras seguidas, o registro mais recente continua indicando 5 mm naquele dia. |
| **Sensores opcionais** | Uma medição igual a zero vale zero. Um sensor ausente aparece como `null`. O banco conserva a precisão de ponto flutuante dos valores convertidos. |
| **Validação** | Um valor inválido ou uma chave repetida entre os campos conhecidos causa HTTP 422. Uma transmissão contendo apenas MAC e data também recebe 422. |
| **Rastreabilidade** | `raw_payload` preserva os parâmetros decodificados, inclusive a sequência de valores de uma chave desconhecida repetida. O log identifica os nomes dos campos desconhecidos. Uma transmissão com identificação válida e apenas sensores desconhecidos fica disponível para diagnóstico no banco. |
| **Retransmissão** | Estação e observação são gravadas na mesma transação. A chave única `(station_id, measured_at_utc)` preserva a primeira leitura aceita naquele segundo, mesmo que uma retransmissão simultânea traga campos adicionais. Essa chave também indexa a consulta por período. |
| **Horários** | `measured_at_utc` vem do console. `received_at_utc` registra a primeira recepção da leitura. `last_seen_at` acompanha o contato mais recente com a estação, inclusive reenvios. |

Para acrescentar suporte a um sensor, inclua seu mapeamento no catálogo, adicione a coluna e o campo no schema de resposta, crie a migração e teste com uma transmissão representativa. [Catálogo de sensores](app/integrations/ambient_weather/fields.py) · [Schemas e unidades públicas](app/schemas.py)

<a id="console"></a>

## Conectar o console físico na futura implantação

Em produção, ajuste `INGEST_HOST` para a interface da LAN e acrescente o IP do console a `INGEST_NETWORKS` antes de iniciar `python -m app.serve ingest`.

Em **Setup → Weather Server → Customized**, habilite o envio personalizado, preencha os campos e salve.

| Campo | Configuração inicial |
|---|---|
| State | Enable |
| Protocol Type | Same As AMBWeather |
| IP/Hostname | 192.168.1.100 |
| Port | 8001 |
| Interval | 60 Second |
| Path | /data/report/ |

Substitua o IP ilustrativo pelo IPv4 da interface do computador que atende a estação. O intervalo de 60 s depende das opções do console. Reserve esse IP no DHCP para continuar recebendo após reinicializações. Aguarde pelo menos um intervalo e consulte `GET /api/v1/stations` no leitor (porta 8080) para obter o ID da estação cadastrada pelo primeiro envio válido. [Manual oficial WS-2000 v2.20, pp. 48–50](https://ambientweather.com/mwdownloads/download/link/id/1113/#page=48)

O endereço de escuta `127.0.0.1` atende somente o próprio computador. Com `0.0.0.0`, o Uvicorn escuta nas interfaces disponíveis. O console precisa alcançar o IP real do computador na mesma LAN ou por uma rota permitida. Libere TCP 8001 no firewall apenas para os equipamentos que precisam dele. O comando `app.serve ingest` desativa cabeçalhos de proxy e usa a origem da conexão TCP.

<a id="rede"></a>

## Configuração e segurança na LAN

| Variável | Uso |
|---|---|
| DATABASE_URL | No modelo DEV, `sqlite:///./data/weather-dev.db`. No modelo PROD, `sqlite:///./data/weather.db`. Caminhos relativos partem da pasta de execução |
| INGEST_NETWORKS | Array JSON de IPs/CIDRs confiáveis. O exemplo permite loopback. Acrescente o IP do console, por exemplo `["192.168.1.45/32","127.0.0.1/32"]` |
| CORS_ORIGINS | Array JSON. Permite `http://localhost:5173` por padrão |
| MAX_QUERY_BYTES, MAX_PARAMETERS | Limites do receptor. Padrões de 8192 bytes e 128 parâmetros. Query longa recebe 414. Excesso de parâmetros ou corpo recebe 413 |
| MAX_PAGE_SIZE | Teto de registros por página. Padrão 500 |
| ACK_TEXT | Texto de confirmação HTTP 200, inicialmente `OK` |
| DIAGNOSTIC_PAYLOAD | `true` registra as medições normalizadas dos sensores presentes. Para inspecionar os parâmetros originais, consulte `observations.raw_payload` no banco |
| ALLOW_SIMULATED | `true` no modelo DEV e `false` no modelo PROD |

As configurações vêm do ambiente ou do arquivo `.env`. Reinicie o processo após alterá-las. HTTP na LAN transmite dados sem criptografia. Um MAC pode ser imitado. A origem da conexão e as regras do firewall limitam a ingestão, sem exigir cabeçalhos que o console pode não oferecer. Proteja o banco e seus backups, pois o payload original pode conter identificadores e campos enviados pelo equipamento.

O túnel HTTPS encaminha exclusivamente para o leitor em `127.0.0.1:8080`. A API pública aceita consultas anônimas com limites de taxa, período e volume. CORS controla o acesso pelo navegador. A ingestão permanece privada.

<a id="diagnostico"></a>

## Diagnóstico de ponta a ponta

Na instalação com dois serviços, rode as sondas na porta 8001 a partir de uma origem autorizada. Se a ingestão escutar somente na interface LAN, use o IP dessa interface.

1. **IP do servidor.** No Windows, use `ipconfig` e identifique o IPv4 da interface da LAN. No Linux, use `ip -br addr`. Confira IP, porta e caminho no console.
2. **Processo e banco.** No servidor, consulte `Invoke-RestMethod http://127.0.0.1:8001/ready` ou `curl -i http://127.0.0.1:8001/ready`. Se `/health` responde e `/ready` devolve 503, confira `DATABASE_URL`, permissões da pasta, credenciais e `python -m alembic current`.
3. **Porta e firewall.** De outro equipamento na mesma rede, execute `Test-NetConnection 192.168.1.100 -Port 8001` ou `curl --connect-timeout 3 http://192.168.1.100:8001/health`. No servidor, veja `Get-NetTCPConnection -LocalPort 8001` ou `ss -ltn`. Verifique o perfil de rede e as regras de entrada em `wf.msc` no Windows ou `sudo ufw status verbose` em distribuições com UFW.
4. **Transmissão do console.** Observe o terminal por dois intervalos. Sem requisição, confira Wi-Fi do console, isolamento de clientes na rede de convidados, roteamento, DHCP e State. Com 403, confira a origem permitida. Com 404, confira o caminho e se o firmware montou a query corretamente. O projeto de referência relata que seu console exigiu um `?` final no Path. Se o firmware concatenar os parâmetros ao caminho, experimente `/data/report/?` e confira novamente. [Referência complementar de servidor local](https://philosowaffle.github.io/ambientweather-local-server/install/setup-ambientweather-console.html)
5. **Protocolo e firmware.** Em 422, confira `ingestion_rejected`, a configuração Same As AMBWeather, MAC e data UTC. `unknown_fields` identifica novos sensores. Ative o diagnóstico temporariamente se os valores convertidos parecerem incorretos. Anote versões do console e do módulo Wi-Fi antes de consultar o suporte. O histórico oficial associa a configuração de Path à versão 1.7.6 do console e Wi-Fi 4.2.8 ou superior. [Suporte oficial da WS-2000](https://ambientweather.com/support/ws-2000-weather-station-support)
6. **Persistência e consulta.** `observation_saved` indica commit e `observation_duplicate` indica reenvio. Leia `station_id` no log e consulte `/api/v1/stations/{id}/latest` no leitor. Para conferir o arquivo SQLite diretamente, execute na raiz:

```bash
python -c "import sqlite3; c=sqlite3.connect('file:data/weather.db?mode=ro', uri=True); print(c.execute('SELECT station_id, count(*), max(measured_at_utc) FROM observations GROUP BY station_id').fetchall())"
```

<a id="testes"></a>

## Testes automatizados

No Windows, execute `.\.venv\Scripts\python -m pytest -q`. No Linux com ambiente ativo, use `python -m pytest -q`. Os testes HTTPX usam SQLite temporário criado pelas migrações, exercitam concorrência, rollback, consultas e CSV.

O teste opcional de PostgreSQL usa `TEST_POSTGRES_URL=postgresql+psycopg://usuario:senha@localhost:5432/weather_test`. Use um banco de testes e um usuário com permissão de criar esquemas. O teste cria e remove seu próprio esquema exclusivo. Sem a variável, o Pytest pula esse teste.

<a id="postgresql"></a>

## Transferir o histórico para PostgreSQL

1. Crie um banco PostgreSQL vazio, um usuário proprietário do esquema e um backup do SQLite. Para tirar um backup consistente com o módulo padrão, use:
   ```bash
   python -c "import sqlite3; a=sqlite3.connect('file:data/weather.db?mode=ro', uri=True); b=sqlite3.connect('data/weather-backup.db'); a.backup(b); b.close(); a.close()"
   ```
2. Para a cópia definitiva, pause o receptor e repita o backup para incluir as últimas leituras. Em uma sessão de terminal, configure as URLs. No PowerShell:
   ```powershell
   $env:SOURCE_DATABASE_URL = 'sqlite:///./data/weather-backup.db'
   $env:DATABASE_URL = 'postgresql+psycopg://usuario:senha@localhost:5432/weather_db'
   .\.venv\Scripts\python -m alembic upgrade head
   .\.venv\Scripts\python scripts/transfer_history.py
   ```
   No Bash:
   ```bash
   export SOURCE_DATABASE_URL='sqlite:///./data/weather-backup.db'
   export DATABASE_URL='postgresql+psycopg://usuario:senha@localhost:5432/weather_db'
   python -m alembic upgrade head
   python scripts/transfer_history.py
   ```
3. Alembic cria o esquema. O script copia os registros em lotes, primeiro estações e depois observações, preservando IDs, chaves estrangeiras, horários e payload JSON. Ele exige a mesma revisão suportada nas duas bases e tabelas de destino vazias. Confere as contagens e ajusta as sequências de IDs antes do commit.
4. Compare as contagens informadas, o intervalo histórico, amostras de `latest` e linhas de CSV com o backup. Persista a nova `DATABASE_URL` no ambiente do serviço, reinicie e confirme `/ready` e o primeiro upload. Guarde o SQLite original. Durante o corte, leituras enviadas com o serviço parado dependem de reenvio pelo console. Para voltar após já receber dados novos em PostgreSQL, preserve essas leituras antes da troca.

<a id="estrutura"></a>

## Organização do repositório

```text
app/main.py                        aplicação, Swagger, logs HTTP e sondas
app/api/                           ingestão e rotas REST versionadas
app/core/                          configuração, redes confiáveis e logs JSON
app/integrations/ambient_weather/  parser, catálogo de campos e conversões
app/db/                            modelos, tipos UTC, conexão e sessões
app/schemas.py                     validação e respostas Pydantic
app/services/                      ingestão transacional e serialização CSV
app/repositories/                  escrita idempotente e consultas SQL
alembic/                           ambiente, template e migração inicial
scripts/                           simulador HTTP e cópia do histórico
tests/                             protocolo, API, banco, migrações e concorrência
data/                              bancos SQLite locais ignorados pelo Git
.env.example                       configuração inicial
pyproject.toml                     instalação e dependências
```

<a id="parceria"></a>

## Parceria

<p align="center">
  <img src="docs/imagens/parceria-ufrpe-uast-sesc.png" alt="Parceria entre a UFRPE, Unidade Acadêmica de Serra Talhada (UAST), e o Sesc" width="440">
</p>
