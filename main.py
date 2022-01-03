import argparse
from jsoncomment import JsonComment
from json import JSONDecodeError
import logging
import colorlog
import os
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

env = Environment(
    loader=PackageLoader("main"),
    autoescape=select_autoescape()
)
logger: logging.Logger


def setup_logging(logfile, debug, color):
    global logger
    print("Setup logging (debug is %s)" % (debug,))
    logger = logging.getLogger()
    logger.propagate = False
    handler = logging.StreamHandler()
    if color:
        handler.setFormatter(
            colorlog.ColoredFormatter(
                '%(asctime)s.%(msecs)03d %(log_color)s[%(name)s:%(levelname)s]%(reset)s %(message)s',
                datefmt='%H:%M:%S'))
    else:
        handler.setFormatter(logging.Formatter(fmt="%(asctime)s.%(msecs)03d [%(name)s:%(levelname)s] %(message)s",
                                               datefmt='%H:%M:%S'))

    file_handler = logging.FileHandler(logfile, "w")
    file_handler.setFormatter(logging.Formatter(fmt="%(asctime)s.%(msecs)03d [%(name)s:%(levelname)s] %(message)s"))

    logger.addHandler(handler)
    logger.addHandler(file_handler)

    if not debug:
        logger.setLevel(logging.INFO)
    else:
        logger.info("Debug logging is ON")
        logger.setLevel(logging.DEBUG)

    # logging.getLogger("urllib3").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(prog='sdvmod.py', description='Stardew Valley Mod List Generator v1.0', )
    parser.add_argument('-g', '--gamedir', help='Game directory', default=r'g:\Steam\steamapps\common\Stardew Valley')
    parser.add_argument('-c', '--config', help='Path to config file', default='config.json')
    parser.add_argument('-o', '--outfile', help='Output file name', default='index.html')

    args = parser.parse_args()

    mydir = Path(__file__).parent
    configfile = Path(args.config)
    outfile = Path(args.outfile)

    if not configfile.is_absolute():
        configfile = mydir / configfile

    if not outfile.is_absolute():
        outfile = mydir / outfile

    gamedir = Path(args.gamedir)

    if not (gamedir / 'Stardew Valley.exe'):
        logger.critical(f'Invalid game directory {gamedir}: missing "Stardew Valley.exe"')
        exit(1)

    if not (gamedir / 'StardewModdingAPI.exe'):
        logger.critical(f'Invalid game directory {gamedir}: missing "StardewModdingAPI.exe" - did you install SMAPI?')
        exit(1)

    config = {'Framework': []}
    if configfile.is_file():
        with configfile.open('r') as f:
            try:
                json = JsonComment()
                config = json.load(f)
            except JSONDecodeError:
                logger.exception(f'Invalid config file {configfile}')
    else:
        logger.warning('Config file not found')

    res = {'Framework': [], 'Content': [], 'Regular': []}

    for p in (gamedir / 'Mods').glob('*' + os.sep + 'manifest.json'):
        logger.debug(f'Loading manifest file {p.relative_to(gamedir / "Mods")}')
        with p.open(encoding='utf-8-sig') as f:
            json = JsonComment()
            try:
                manifest = json.load(f)
            except JSONDecodeError:
                tempname = str(p.relative_to(gamedir / "Mods")).replace(os.sep, '_')
                f.seek(0)
                lines = f.read().splitlines()
                # noinspection PyProtectedMember
                rez = json._preprocess(lines)
                with open(tempname, 'w') as g:
                    g.write(rez)
                logger.exception(f'Invalid mod manifest: {p.relative_to(gamedir / "Mods")}; dumped to {tempname}')
                manifest = None

        if not manifest:
            continue

        mod = {'name': manifest['Name'], 'version': manifest['Version'],
               'description': manifest.get('Description', '???')}

        try:
            mod_link = manifest['UpdateKeys'][0].lower()
            if mod_link.startswith('chucklefish'):
                mod_link = 'https://community.playstarbound.com/resources/{0}/'.format(mod_link.split(':')[1])
            elif mod_link.startswith('nexus'):
                mod_link = 'https://www.nexusmods.com/stardewvalley/mods/{0}'.format(mod_link.split(':')[1])
            elif mod_link.startswith('github'):
                mod_link = 'https://github.com/{0}/releases'.format(mod_link.split(':')[1])
            else:
                logger.error(f"ERROR: Unknown update key {mod_link}")
        except (IndexError, KeyError):
            logger.error("ERROR: Missing or invalid update key " + str(manifest.get('UpdateKeys', 'None')))
            mod_link = ''

        mod['url'] = mod_link

        if 'ContentPackFor' in manifest:
            res['Content'].append(mod)
        else:
            if manifest['Name'] in config['Framework']:
                res['Framework'].append(mod)
            else:
                res['Regular'].append(mod)

    template = env.get_template("index.html")
    with outfile.open(mode='w', encoding='utf8') as f:
        f.write(template.render(coremods=res['Framework'], cpacks=res['Content'], mods=res['Regular']))


if __name__ == '__main__':
    setup_logging(logfile='StardewValleyMods.log', debug=True, color=True)
    main()
