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
    <a href="#instalacao">Começar agora</a> ·
    <a href="#console">Conectar a estação</a> ·
    <a href="#simulador">Testar com o simulador</a> ·
    <a href="#consultas">Consultar a API</a>
  </p>
</div>

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
- [Consultas, unidades e exportação CSV](#consultas)
- [Protocolo e regras de armazenamento](#armazenamento)
- [Configuração da rede local](#rede) e [diagnóstico](#diagnostico)
- [Testes automatizados](#testes) e [migração para PostgreSQL](#postgresql)
- [Organização do repositório](#estrutura) e [parceria](#parceria)

<a id="instalacao"></a>

## Instalação

Use Python **3.12 ou superior** e execute os comandos na raiz do repositório. O SQLite acompanha o Python. Para receber dados reais, o computador precisa estar acessível ao console pela rede local. Para experimentar a API, basta usar o simulador.

### Windows · PowerShell

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[test]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

Os comandos usam o interpretador do ambiente virtual diretamente. Mantenha o terminal do Uvicorn aberto enquanto estiver recebendo dados.

<details>
<summary><strong>Linux · Bash</strong></summary>

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
test -f .env || cp .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

</details>

O Alembic cria o esquema em `data/weather.db`. Aplique as migrações antes de iniciar uma versão atualizada da API. Com o servidor em execução, confira se o banco responde e explore os endpoints no navegador. [Prontidão do serviço](http://127.0.0.1:8000/ready) · [Swagger local](http://127.0.0.1:8000/docs)

<a id="console"></a>

## Conectar o console físico

Em **Setup → Weather Server → Customized**, habilite o envio personalizado, preencha os campos e salve.

| Campo | Configuração inicial |
|---|---|
| State | Enable |
| Protocol Type | Same As AMBWeather |
| IP/Hostname | 192.168.1.100 |
| Port | 8000 |
| Interval | 60 Second |
| Path | /data/report/ |

Substitua o IP ilustrativo pelo IPv4 da interface do computador que atende a estação. O intervalo de 60 s depende das opções do console. Reserve esse IP no DHCP para continuar recebendo após reinicializações. Aguarde pelo menos um intervalo e consulte `GET /api/v1/stations` para obter o ID da estação cadastrada pelo primeiro envio válido. [Manual oficial WS-2000 v2.20, pp. 48–50](https://ambientweather.com/mwdownloads/download/link/id/1113/#page=48)

O endereço de escuta `127.0.0.1` atende somente o próprio computador. Com `0.0.0.0`, o Uvicorn escuta nas interfaces disponíveis. O console precisa alcançar o IP real do computador na mesma LAN ou por uma rota permitida. Libere TCP 8000 no firewall apenas para os equipamentos que precisam dele. Use `--no-proxy-headers` na ligação direta para que a lista de redes use a origem da conexão TCP.

<a id="simulador"></a>

## Conferir o fluxo com o simulador

Para o primeiro ensaio, use uma sessão de terminal separada e um banco exclusivo. No PowerShell, configure e inicie o receptor de desenvolvimento:

```powershell
$env:DATABASE_URL = 'sqlite:///./data/simulacao.db'
$env:ALLOW_SIMULATED = 'true'
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-proxy-headers
```

No Bash com o ambiente virtual ativo, use `export DATABASE_URL=sqlite:///./data/simulacao.db` e `export ALLOW_SIMULATED=true`, seguidos de `python -m alembic upgrade head` e `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-proxy-headers`.

Em outro terminal, com o Python do projeto:

```bash
python scripts/simulate_station.py --url http://127.0.0.1:8001 --mac 02:00:00:00:20:00 --interval 2 --samples 3 --field tempf=86 --field windgustmph=15
```

O script envia uma amostra por requisição, com o relógio UTC atual, MAC local fictício e `dev_simulated=1`. Cada `--field` acrescenta ou substitui um parâmetro do fabricante. O servidor recusa simulações por padrão e impede misturar dados reais e simulados sob o mesmo MAC. A identificação de desenvolvimento aparece em `stations.is_simulated`. Exemplo de uma transmissão reproduzível, contra a instância de desenvolvimento:

```text
GET /data/report/?MAC=02%3A00%3A00%3A00%3A20%3A00&dateutc=2026-11-20+14%3A30%3A00&tempf=86&humidity=60&windspeedmph=12&dailyrainin=0.10&dev_simulated=1
```

A resposta padrão é HTTP 200 com texto `OK`. Em `/api/v1/stations/1/latest`, esses valores correspondem a 30 °C, 60%, 5,36448 m/s e 2,54 mm. Use o ID devolvido por `/api/v1/stations` se houver outras estações. Ao encerrar o ensaio, feche o terminal do receptor de desenvolvimento para descartar suas variáveis temporárias.

<a id="consultas"></a>

## Consultas e exportação

O frontend recebe temperatura em °C, velocidade e rajada em m/s, direção em graus, chuva acumulada em mm, pressão em hPa, umidade em %, radiação solar em W/m² e índice UV adimensional. As observações e as estatísticas usam essas unidades desde a gravação. No OpenAPI, cada campo meteorológico declara sua unidade na descrição e na propriedade `x-unit`. O CSV inclui a unidade no cabeçalho.

As respostas JSON trazem os instantes em UTC com sufixo `Z`. Para exibir o horário de Brasília, o frontend pode usar `new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", timeStyle: "medium" }).format(new Date(observacao.measured_at_utc))`. Assim, `2026-11-20T14:30:00Z` aparece como `11:30:00` para o usuário.

| GET | Resultado |
|---|---|
| `/health` | Processo em execução |
| `/ready` | Acesso às tabelas de estações e observações. HTTP 503 em caso de falha |
| `/api/v1/stations` | Estações e horário de última transmissão aceita, inclusive retransmissões |
| `/api/v1/stations/{id}` | Identificação, modelo, origem e horários da estação |
| `/api/v1/stations/{id}/latest` | Última observação inserida, ordenada por recebimento e ID |
| `/api/v1/stations/{id}/observations` | Histórico com `page`, `page_size`, `order=asc\|desc`, `start` e `end` |
| `/api/v1/stations/{id}/summary` | Contagem, mínima/média/máxima externas de temperatura e umidade, vento médio/máximo e última observação recebida no período |
| `/api/v1/stations/{id}/export.csv` | CSV UTF-8 em ordem de medição, com cabeçalhos e unidades |
| `/openapi.json` | Contrato da API para integração |

`start` e `end` são inclusivos e filtram **o instante da medição** no histórico, no resumo e no CSV. Use ISO 8601 com fuso explícito, por exemplo `2026-11-20T14:30:00Z`. Uma leitura antiga que chegar atrasada pode aparecer em `latest`. A paginação começa em 1. O tamanho padrão é o menor entre 100 e `MAX_PAGE_SIZE`. Cada página contém `page`, `page_size` e `items`. Uma estação inexistente retorna 404. Um período vazio retorna lista vazia, contagem zero e estatísticas nulas. Médias excluem sensores ausentes.

```bash
curl 'http://127.0.0.1:8000/api/v1/stations/1/observations?start=2026-11-01T00:00:00Z&end=2026-11-20T23:59:59Z&page=1&page_size=100'
curl -o novembro.csv 'http://127.0.0.1:8000/api/v1/stations/1/export.csv?start=2026-11-01T00:00:00Z&end=2026-11-30T23:59:59Z'
```

No PowerShell, use `Invoke-RestMethod` para JSON e `Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/stations/1/export.csv' -OutFile leituras.csv` para o CSV. A exportação é transmitida em lotes de 256 linhas. No Excel ou LibreOffice, selecione UTF-8, separador vírgula e ponto decimal na importação.

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

<a id="rede"></a>

## Configuração e segurança na LAN

| Variável | Uso |
|---|---|
| DATABASE_URL | Padrão `sqlite:///./data/weather.db`. Caminhos relativos partem da pasta de execução |
| INGEST_NETWORKS | Array JSON de IPs/CIDRs confiáveis. O exemplo atende loopback e redes IPv4 privadas. Prefira restringir ao IP do console, por exemplo `["192.168.1.45/32","127.0.0.1/32"]` |
| CORS_ORIGINS | Array JSON. Permite `http://localhost:5173` por padrão |
| MAX_QUERY_BYTES, MAX_PARAMETERS | Limites do receptor. Padrões de 8192 bytes e 128 parâmetros. Query longa recebe 414. Excesso de parâmetros ou corpo recebe 413 |
| MAX_PAGE_SIZE | Teto de registros por página. Padrão 500 |
| ACK_TEXT | Texto de confirmação HTTP 200, inicialmente `OK` |
| DIAGNOSTIC_PAYLOAD | `true` registra as medições normalizadas dos sensores presentes. Para inspecionar os parâmetros originais, consulte `observations.raw_payload` no banco |
| ALLOW_SIMULATED | `false` por padrão. Habilite apenas na instância de desenvolvimento |

As configurações vêm do ambiente ou do arquivo `.env`. Reinicie o processo após alterá-las. HTTP na LAN transmite dados sem criptografia. Um MAC pode ser imitado. A origem da conexão e as regras do firewall limitam a ingestão, sem exigir cabeçalhos que o console pode não oferecer. Proteja o banco e seus backups, pois o payload original pode conter identificadores e campos enviados pelo equipamento.

Mantenha a porta fora da internet pública, sem encaminhamento no roteador. As consultas da primeira versão são abertas aos clientes com acesso à porta. CORS é uma política de navegador. Para publicação futura, aplique HTTPS, autenticação, permissões e limites de taxa no roteador de consultas ou no proxy, mantendo o receptor da estação em rede privada.

<a id="diagnostico"></a>

## Diagnóstico de ponta a ponta

1. **IP do servidor.** No Windows, use `ipconfig` e identifique o IPv4 da interface da LAN. No Linux, use `ip -br addr`. Confira IP, porta e caminho no console.
2. **Processo e banco.** No servidor, consulte `Invoke-RestMethod http://127.0.0.1:8000/ready` ou `curl -i http://127.0.0.1:8000/ready`. Se `/health` responde e `/ready` devolve 503, confira `DATABASE_URL`, permissões da pasta, credenciais e `python -m alembic current`.
3. **Porta e firewall.** De outro equipamento na mesma rede, execute `Test-NetConnection 192.168.1.100 -Port 8000` ou `curl --connect-timeout 3 http://192.168.1.100:8000/health`. No servidor, veja `Get-NetTCPConnection -LocalPort 8000` ou `ss -ltn`. Verifique o perfil de rede e as regras de entrada em `wf.msc` no Windows ou `sudo ufw status verbose` em distribuições com UFW.
4. **Transmissão do console.** Observe o terminal por dois intervalos. Sem requisição, confira Wi-Fi do console, isolamento de clientes na rede de convidados, roteamento, DHCP e State. Com 403, confira a origem permitida. Com 404, confira o caminho e se o firmware montou a query corretamente. O projeto de referência relata que seu console exigiu um `?` final no Path. Se o firmware concatenar os parâmetros ao caminho, experimente `/data/report/?` e confira novamente. [Referência complementar de servidor local](https://philosowaffle.github.io/ambientweather-local-server/install/setup-ambientweather-console.html)
5. **Protocolo e firmware.** Em 422, confira `ingestion_rejected`, a configuração Same As AMBWeather, MAC e data UTC. `unknown_fields` identifica novos sensores. Ative o diagnóstico temporariamente se os valores convertidos parecerem incorretos. Anote versões do console e do módulo Wi-Fi antes de consultar o suporte. O histórico oficial associa a configuração de Path à versão 1.7.6 do console e Wi-Fi 4.2.8 ou superior. [Suporte oficial da WS-2000](https://ambientweather.com/support/ws-2000-weather-station-support)
6. **Persistência e consulta.** `observation_saved` indica commit e `observation_duplicate` indica reenvio. Leia `station_id` no log e consulte `latest` no Swagger. Para conferir o arquivo SQLite diretamente, execute na raiz:

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
3. Alembic cria o esquema. O script copia os registros em lotes, primeiro estações e depois observações, preservando IDs, chaves estrangeiras, horários e payload JSON. Ele exige a revisão inicial nas duas bases e tabelas de destino vazias. Confere as contagens e ajusta as sequências de IDs antes do commit.
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
