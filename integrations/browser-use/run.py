"""Run the Browser Use client alongside an existing Lupa Compose container."""
import argparse
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
source = Path(__file__).resolve().parent
image = 'lupa-browser-use:0.13.10'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', help='Container ID/name; defaults to docker compose ps -q lupa')
    parser.add_argument('--build', action='store_true', help='Rebuild the client image')
    parser.add_argument('action', nargs=argparse.REMAINDER, help='leads --query TEXT --municipality CITY --output /output/DIR, demo, inspect, open URL, click SELECTOR, fill SELECTOR TEXT, press KEY, scroll PIXELS, screenshot /output/FILE.png')
    args = parser.parse_args()
    if not args.action:
        parser.error('Indica una acción, por ejemplo demo')
    container = args.container or subprocess.check_output(
        ['docker', 'compose', 'ps', '-q', 'lupa'], cwd=root, text=True,
    ).strip()
    if not container or '\n' in container:
        parser.error('Se necesita una instancia de Lupa en ejecución; usa --container si hay varias')
    exists = subprocess.run(['docker', 'image', 'inspect', image], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if args.build or not exists:
        subprocess.run(['docker', 'build', '--network', 'host', '-t', image, str(source)], check=True)
    # Capture the secret internally and transmit it over stdin, never argv or logs.
    token = subprocess.check_output([
        'docker', 'exec', container, '/config/.bun/bin/bun', '-e',
        'import {readFileSync} from "node:fs"; const t=process.env.LUPA_API_TOKEN_FILE?readFileSync(process.env.LUPA_API_TOKEN_FILE,"utf8").trim():process.env.LUPA_API_TOKEN; if(!t)process.exit(1);process.stdout.write(t);',
    ])
    output = root / 'downloads'
    output.mkdir(exist_ok=True)
    result = subprocess.run([
        'docker', 'run', '--rm', '-i', '--network', 'container:' + container,
        '-v', str(source) + ':/client:ro', '-v', str(output) + ':/output',
        image, *args.action,
    ], input=token + b'\n')
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
