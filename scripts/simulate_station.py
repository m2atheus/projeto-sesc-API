"""Envia transmissões identificadas como simulações a uma instância de desenvolvimento."""
import argparse
import math
import time
from datetime import UTC, datetime
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="URL base do servidor")
    parser.add_argument("--mac", default="02:00:00:00:20:00")
    parser.add_argument("--interval", type=float, default=60, help="Segundos entre amostras")
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--field", action="append", default=[], metavar="NOME=VALOR")
    args = parser.parse_args()
    if args.samples < 1 or not math.isfinite(args.interval) or args.interval < 1:
        parser.error("--samples e --interval devem ser pelo menos 1")
    sensors = {"tempf": "86", "humidity": "60", "windspeedmph": "12", "dailyrainin": "0.10"}
    for field in args.field:
        name, sep, value = field.partition("=")
        if not sep or not name or name in {"MAC", "dateutc", "dev_simulated"}:
            parser.error("Campo inválido ou reservado")
        sensors[name] = value

    for index in range(args.samples):
        params = dict(sensors, MAC=args.mac, dateutc=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                      dev_simulated="1")
        url = args.url.rstrip("/") + "/data/report/?" + urlencode(params)
        try:
            with urlopen(url, timeout=15) as response:
                print(f"Amostra {index + 1}: HTTP {response.status} {response.read(256).decode()}")
        except URLError as exc:
            parser.exit(1, f"Falha no envio: {exc}\n")
        if index + 1 < args.samples:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
