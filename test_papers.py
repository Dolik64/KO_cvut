#!/usr/bin/env python3
"""Diagnostika Papers pro Linux, Python 3.8+, pouze standardni knihovna.

Spusteni: python3 test_papers.py
Volby: --pdf-dir CESTA --seconds 25 --auto --rounds 2
Report TXT se vzdy uklada vedle tohoto skriptu. PDF se neupravuji.
Bez sudo, instalace balicku a zmen Flatpak override / GSettings.
Papers si pri beznem pouzivani muze sam ukladat historii a stav dokumentu.
"""
import argparse
import datetime as dt
import os
from pathlib import Path
import select
import shlex
import shutil
import signal
import statistics
import subprocess as sp
import sys
import tempfile
import time

APP = 'org.gnome.Papers'
DEFAULT_DIR = Path.home() / 'Documents/CVUT OI/magistr/1 semestr/KO'
PDF_NAMES = ['Příklady (1).pdf', 'koa_test12.pdf']
VARIANTS = [
    ('aktualni', []),
    ('simple_OpenGL', ['--env=GTK_IM_MODULE=gtk-im-context-simple', '--env=GSK_RENDERER=gl']),
    ('simple_Vulkan', ['--env=GTK_IM_MODULE=gtk-im-context-simple', '--env=GSK_RENDERER=vulkan']),
    ('IBus_OpenGL', ['--env=GTK_IM_MODULE=ibus', '--env=GSK_RENDERER=gl']),
]
LOG = None


def log(message='', console=False):
    if LOG:
        LOG.write(str(message) + '\n')
        LOG.flush()
    if console:
        print(message, flush=True)


def capture(cmd, timeout=15):
    start = time.monotonic()
    try:
        result = sp.run(cmd, stdout=sp.PIPE, stderr=sp.STDOUT,
                        text=True, errors='replace', timeout=timeout)
        return result.returncode, result.stdout, time.monotonic() - start
    except sp.TimeoutExpired as ex:
        out = ex.stdout or b''
        if isinstance(out, bytes):
            out = out.decode(errors='replace')
        return 124, out + '\nTIMEOUT', time.monotonic() - start
    except OSError as ex:
        return 127, str(ex), time.monotonic() - start


def diagnostic(cmd, timeout=15):
    rc, out, elapsed = capture(cmd, timeout)
    log('\n$ ' + shlex.join(cmd))
    log('exit=%s, doba=%.3f s\n%s' % (rc, elapsed, out))
    return rc, out


def instances():
    rc, out, _ = capture(['flatpak', 'ps', '--columns=instance,application,pid'])
    if rc:
        raise RuntimeError('Nelze zjistit bezici Flatpak instance: ' + out)
    return [line.split() for line in out.splitlines()
            if len(line.split()) >= 3 and line.split()[1] == APP]


def proc_table():
    result = {}
    for item in Path('/proc').iterdir():
        if not item.name.isdigit():
            continue
        try:
            raw = (item / 'stat').read_text()
            name = raw[raw.index('(') + 1:raw.rindex(')')]
            fields = raw[raw.rindex(')') + 2:].split()
            result[int(item.name)] = {
                'ppid': int(fields[1]), 'cpu': int(fields[11]) + int(fields[12]),
                'start': int(fields[19]), 'rss': int(fields[21]) * os.sysconf('SC_PAGE_SIZE'),
                'name': name,
            }
        except (OSError, ValueError, IndexError):
            continue
    return result


def descendants(table, roots):
    found = set(roots) & set(table)
    while True:
        more = {pid for pid, data in table.items() if data['ppid'] in found}
        new = more - found
        if not new:
            return found
        found.update(new)


def pressure():
    mem = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        parts = line.split()
        mem[parts[0].rstrip(':')] = int(parts[1])
    return mem.get('MemAvailable', 0) / 1024, (mem.get('SwapTotal', 0) - mem.get('SwapFree', 0)) / 1024


def journal(since, until):
    diagnostic(['journalctl', '--user', '-b', '--since', '@%.6f' % since,
                '--until', '@%.6f' % until, '--no-pager', '-o', 'short-precise',
                '-n', '120', '--grep', 'IBus|ibus|papers|Papers|portal|Vulkan|vulkan'])


def trial(pdf, name, options, seconds, automatic):
    if instances():
        raise RuntimeError('Pred dalsim testem stale bezi Papers. Zavri ho a spust skript znovu.')
    log('\n' + '=' * 70)
    log('TEST: %s | %s' % (pdf.name, name), True)
    if not automatic:
        input('Enter = spustit test. Po vykresleni stranky se vrat sem a znovu stiskni Enter. ')
    log('Pri testu nic neupravuj, nescrolluj ani nezoomuj.', True)
    wall_start = time.time()
    samples, ready, process_time, instance = [], None, None, ''
    rfd, wfd = os.pipe()
    os.set_blocking(rfd, False)
    proc = None
    prev = {}
    prev_time = time.monotonic()
    instance_bytes = b''
    root_pid = None
    try:
        with tempfile.TemporaryFile(mode='w+b') as app_log:
            cmd = ['flatpak', 'run', '--instance-id-fd=%d' % wfd, *options,
                   APP, str(pdf)]
            log('$ ' + shlex.join(cmd))
            start = time.monotonic()
            proc = sp.Popen(cmd, stdout=app_log, stderr=sp.STDOUT,
                            stdin=sp.DEVNULL, pass_fds=(wfd,), start_new_session=True)
            os.close(wfd)
            wfd = None
            next_ps = start
            log('t_s  RSS_MiB  CPU_pct_1core  available_MiB  swap_MiB  PIDs')
            while time.monotonic() - start < seconds:
                now = time.monotonic()
                try:
                    chunk = os.read(rfd, 4096)
                    instance_bytes += chunk
                    candidate = instance_bytes.decode(errors='replace').strip()
                    if candidate.isdigit():
                        instance = candidate
                except BlockingIOError:
                    pass
                if now >= next_ps and instance and root_pid is None:
                    for row in instances():
                        if row[0] == instance and row[2].isdigit():
                            root_pid = int(row[2])
                    next_ps = now + 1
                table = proc_table()
                pids = descendants(table, [proc.pid] + ([root_pid] if root_pid else []))
                if process_time is None and any(table[p]['name'] == 'papers' for p in pids):
                    process_time = now - start
                current = {(p, table[p]['start']): table[p]['cpu'] for p in pids}
                # First sample has no CPU interval. Newly appearing children are counted from 0.
                ticks = sum(max(0, value - prev.get(key, 0)) for key, value in current.items()) if prev else 0
                cpu = ticks / os.sysconf('SC_CLK_TCK') / max(now - prev_time, .001) * 100
                rss = sum(max(0, table[p]['rss']) for p in pids) / 1048576
                available, swap = pressure()
                row = (now - start, rss, cpu, available, swap)
                samples.append(row)
                log('%.2f  %.1f  %.1f  %.1f  %.1f  %s' % (*row, sorted(pids)))
                prev, prev_time = current, now
                if not automatic and ready is None and select.select([sys.stdin], [], [], 0)[0]:
                    if sys.stdin.readline() == '':
                        automatic = True
                    else:
                        ready = time.monotonic() - start
                        log('Rucne potvrzene zobrazeni: %.2f s (vcetne reakce a prepnuti okna).' % ready, True)
                if proc.poll() is not None:
                    log('Spousteci proces skoncil pred koncem testu, exit=%s.' % proc.returncode, True)
                    break
                if available < 350:
                    log('Test ukoncen: dostupna RAM klesla pod 350 MiB.', True)
                    break
                time.sleep(.5)
            natural_exit = proc.poll()
            log('Stav procesu pred ukoncenim testu: %s' % natural_exit)
            # Close only the instance created by this test, never all Papers windows.
            stop(proc, instance)
            proc = None
            wall_end = time.time()
            app_log.seek(0)
            log('\nSTDOUT/STDERR Papers:\n' + app_log.read(262144).decode(errors='replace'))
            if app_log.read(1):
                log('[Dalsi vystup zkracen na 256 KiB.]')
    finally:
        if proc is not None:
            stop(proc, instance)
        os.close(rfd)
        if wfd is not None:
            os.close(wfd)
    journal(wall_start, wall_end)
    valid = [s for s in samples if s[1] > 0]
    peak = max((s[1] for s in valid), default=0)
    log('Peak RSS celeho stromu = %.1f MiB; sdilena pamet muze byt zapoctena vicekrat.' % peak)
    if len(valid) >= 8:
        late = valid[len(valid) // 2:]
        delta = late[-1][1] - late[0][1]
        log('Zmena RSS v druhe polovine: %+.1f MiB. Toto samo nepotvrzuje memory leak.' % delta)
    else:
        delta = None
    return {'pdf': pdf.name, 'variant': name, 'ready': ready, 'process': process_time,
            'peak': peak, 'delta': delta, 'exit': natural_exit}


def stop(proc, instance):
    # Instance ID belongs to our launch; no app-wide flatpak kill.
    if instance:
        capture(['flatpak', 'kill', instance], 8)
    try:
        proc.wait(timeout=3)
    except sp.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=3)
        except ProcessLookupError:
            pass
        except sp.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=3)


def main():
    global LOG
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pdf-dir', type=Path)
    parser.add_argument('--seconds', type=float, default=25, help='Sekund na jedno otevreni (default 25).')
    parser.add_argument('--rounds', type=int, default=1, help='Pocet kol; 2 otoci poradi variant.')
    parser.add_argument('--auto', action='store_true', help='Bez Enteru; nezmeri skutecne zobrazeni stranky.')
    args = parser.parse_args()
    if args.seconds < 5 or args.rounds < 1:
        parser.error('--seconds musi byt >= 5 a --rounds >= 1')
    base = Path(__file__).resolve().parent
    report = base / ('papers_diagnostika_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.txt')
    with report.open('x', encoding='utf-8', buffering=1) as logfile:
        LOG = logfile
        log('Papers diagnostika | ' + dt.datetime.now().astimezone().isoformat(), True)
        log('Report: ' + str(report), True)
        try:
            if not shutil.which('flatpak'):
                raise RuntimeError('Flatpak nebyl nalezen.')
            if instances():
                raise RuntimeError('Nejdrive zavri vsechna okna Papers a spust skript znovu. Zadna okna jsem nezavrel.')
            candidates = [args.pdf_dir.expanduser()] if args.pdf_dir else [base, Path.cwd(), DEFAULT_DIR]
            folder = next((p for p in candidates if all((p / n).is_file() for n in PDF_NAMES)), None)
            if folder is None:
                raise RuntimeError('PDF nenalezena. Pouzij --pdf-dir "cesta ke slozce KO". Hledano: ' + str(candidates))
            pdfs = [(folder / n).resolve() for n in PDF_NAMES]
            automatic = args.auto or not sys.stdin.isatty()
            log('PDF slozka: ' + str(folder))
            log('Rezim: ' + ('automaticky; cas zobrazeni NEBUDE znam' if automatic else 'rucni potvrzeni zobrazeni'))
            log('Bez zmen nastaveni. Neupravuj dokumenty: testovaci okna budou automaticky ukoncena.', True)
            log('Zaznam obsahuje cesty, technicke parametry a relevantni systemove logy; obsah PDF se nezapisuje.')
            for cmd in [
                ['uname', '-a'], ['flatpak', '--version'], ['flatpak', 'info', APP],
                ['flatpak', 'override', '--user', '--show', APP],
                ['flatpak', 'override', '--system', '--show', APP],
                ['flatpak', 'run', '--command=gsettings', APP, 'get', APP, 'page-cache-size'],
                ['xdg-mime', 'query', 'default', 'application/pdf'],
                ['free', '-h'], ['vmstat', '1', '3'],
                ['ps', '-eo', 'pid,comm,rss,%cpu', '--sort=-rss'],
            ]:
                if cmd[0] == 'ps':
                    rc, out, _ = capture(cmd)
                    log('\nNejvetsi procesy:\n' + '\n'.join(out.splitlines()[:20]))
                else:
                    diagnostic(cmd)
            for var in ['XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP', 'GTK_IM_MODULE', 'GSK_RENDERER', 'GDK_BACKEND']:
                log('%s=%s' % (var, os.environ.get(var, '<nenastaveno>')))
            for p in ['/proc/pressure/memory', '/proc/pressure/io']:
                if Path(p).is_file():
                    log(p + '\n' + Path(p).read_text())
            if shutil.which('nvidia-smi'):
                diagnostic(['nvidia-smi', '--query-gpu=name,driver_version,memory.used,utilization.gpu', '--format=csv'])
            for pdf in pdfs:
                log('\nPDF %s | %d bytes' % (pdf, pdf.stat().st_size))
                if shutil.which('pdfinfo'):
                    rc, out, elapsed = capture(['pdfinfo', str(pdf)], 20)
                    # Keep technical PDF properties, exclude author/title metadata.
                    log('pdfinfo: exit=%s, %.3f s' % (rc, elapsed))
                    for line in out.splitlines():
                        if line.startswith(('Pages:', 'Page size:', 'Page rot:', 'File size:', 'PDF version:', 'Encrypted:', 'Syntax', 'Error')):
                            log(line)
                else:
                    log('pdfinfo nenalezen, preskoceno (nic se neinstaluje).')
                if shutil.which('pdftoppm'):
                    with tempfile.TemporaryDirectory(prefix='papers_render_') as temp:
                        diagnostic(['pdftoppm', '-f', '1', '-l', '1', '-singlefile', '-scale-to', '1600', str(pdf), str(Path(temp) / 'page')], 30)
                    log('Test pouze prvni stranky hostitelskym Popplerem; verze muze byt jina nez ve Flatpaku.')
                else:
                    log('pdftoppm nenalezen, test renderovani preskocen.')
            rows = []
            for cycle in range(args.rounds):
                variants = VARIANTS if cycle % 2 == 0 else list(reversed(VARIANTS))
                for pdf in pdfs:
                    for name, options in variants:
                        rows.append(trial(pdf, name, options, args.seconds, automatic))
            log('\n=== SOUHRN ===', True)
            for row in rows:
                def seconds(value):
                    return 'nezmereno' if value is None else '%.2f s' % value
                log('%s | %s | potvrzena stranka %s | proces %s | peak RSS %.1f MiB | exit pred ukoncenim %s' % (
                    row['pdf'], row['variant'], seconds(row['ready']), seconds(row['process']), row['peak'], row['exit']), True)
            for pdf in pdfs:
                measured = [r for r in rows if r['pdf'] == pdf.name and r['ready'] is not None and r['exit'] is None]
                if measured:
                    scores = {v: statistics.median(r['ready'] for r in measured if r['variant'] == v)
                              for v in {r['variant'] for r in measured}}
                    best = min(scores, key=scores.get)
                    log('Nejnizsi rucne potvrzeny cas pro %s: %s (%.2f s); orientacni, vcetne lidske reakce.' % (pdf.name, best, scores[best]), True)
            log('\nINTERPRETACE:')
            log('IBus_OpenGL vs simple_OpenGL meni pouze vstupni modul. simple_OpenGL vs simple_Vulkan meni pouze renderer.')
            log('Aktualni varianta dedi existujici nastaveni a muze byt shodna s jinou variantou.')
            log('Proces existuje != stranka vykreslena. CPU se meri z rozdilu /proc; 100 % = jedno jadro.')
            log('Zadny kratky rust RSS nedokazuje leak. Cache, GPU pamet a sdilene stranky mohou vysledky ovlivnit.')
            log('Prvni otevreni muze byt pomalejsi kvuli cache. Cache OS se nemaze. Pro kontrolu poradi pouzij --rounds 2.')
            log('Pokud nebyl Enter, neni to dukaz timeoutu vykresleni. Okno mohlo byt prekryte.')
            diagnostic(['free', '-h'])
        except KeyboardInterrupt:
            log('\nPreruseno uzivatelem; castecnou diagnostiku najdes v reportu.', True)
            return 130
        except Exception as ex:
            log('\nCHYBA: %s: %s' % (type(ex).__name__, ex), True)
            return 1
        finally:
            log('\nTXT ulozen: ' + str(report), True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
