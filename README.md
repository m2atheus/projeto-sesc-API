# API meteorológica WS-2000

O console Ambient Weather envia as leituras por HTTP ao computador da rede local. A API FastAPI recebe cada transmissão, converte as unidades, guarda a observação e seus parâmetros originais no SQLite e oferece consultas em JSON e CSV. Após a instalação das dependências, o serviço e o Swagger funcionam sem internet.

## Executar no Windows

Na raiz do repositório, com Python 3.12 ou superior no PATH, execute no PowerShell:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[test]"
Copy-Item .env.example .env
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

Faça a cópia de `.env.example` apenas na primeira instalação. Os comandos usam o interpretador do ambiente diretamente, inclusive quando a política do PowerShell impede a ativação.

## Executar no Linux

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
cp .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

Abra o [Swagger local](http://127.0.0.1:8000/docs) e a [prontidão do serviço](http://127.0.0.1:8000/ready). O Alembic cria o esquema em `data/weather.db`. Execute a migração antes de cada atualização da aplicação.

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

## Protocolo, unidades e persistência

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

Os acumuladores de chuva são preservados por intervalo. O resumo não os soma. Zero, valor ausente e número inválido têm tratamentos distintos. A aplicação conserva a precisão do tipo de ponto flutuante do banco e devolve `null` para sensores ausentes. Um campo conhecido presente com valor inválido rejeita a transmissão inteira com 422. MAC e data sem parâmetros adicionais também recebem 422. Uma transmissão só com sensores desconhecidos é preservada para análise.

`raw_payload` guarda o mapa JSON dos parâmetros decodificados, com grafia e valores originais. Chaves desconhecidas repetidas guardam a sequência de valores. Repetições de campos conhecidos são ambíguas e recebem 422. O log identifica os nomes desconhecidos. O payload bruto fica no banco, fora das respostas de consulta e do CSV. Para mapear um novo sensor, acrescente a especificação em `fields.py`, a coluna e o schema correspondentes, uma migração e um teste com uma transmissão representativa.

Cada upload grava estação e observação na mesma transação. A restrição única em `(station_id, measured_at_utc)` arbitra a concorrência e indexa a busca por período. Para duas transmissões da mesma estação no mesmo segundo, prevalece o primeiro payload aceito, inclusive se a segunda trouxer sensores adicionais. `received_at_utc` conserva a primeira recepção da observação e `last_seen_at` acompanha a comunicação mais recente. SQLite e PostgreSQL devolvem horários com UTC explícito.

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

## Testes

No Windows, execute `.\.venv\Scripts\python -m pytest -q`. No Linux com ambiente ativo, use `python -m pytest -q`. Os testes HTTPX usam SQLite temporário criado pelas migrações, exercitam concorrência, rollback, consultas e CSV.

O teste opcional de PostgreSQL usa `TEST_POSTGRES_URL=postgresql+psycopg://usuario:senha@localhost:5432/weather_test`. Use um banco de testes e um usuário com permissão de criar esquemas. O teste cria e remove seu próprio esquema exclusivo. Sem a variável, o Pytest pula esse teste.

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
