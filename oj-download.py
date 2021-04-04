# Python script for download problemm
# Heavily based on onlinejudge_prepare(https://github.com/online-judge-tools/template-generator/blob/master/onlinejudge_prepare/main.py)
# This script removes the need of config files.

import argparse
import contextlib
import os
import pathlib
import stat
import subprocess
import sys
import urllib.parse
from logging import DEBUG, INFO, basicConfig, getLogger
from typing import *

import appdirs
import colorlog
import requests
import toml

import onlinejudge
import onlinejudge.utils
import onlinejudge_template.analyzer.combined as analyzer
import onlinejudge_template.generator._main as generator
import onlinejudge_template.network as network

logger = getLogger(__name__)


@contextlib.contextmanager
def chdir(dir: pathlib.Path) -> Iterator[None]:
    cwd = pathlib.Path.cwd()
    dir.mkdir(parents=True, exist_ok=True)
    os.chdir(dir)
    try:
        yield
    finally:
        os.chdir(cwd)


def get_directory(*, problem: onlinejudge.type.Problem, contest: Optional[onlinejudge.type.Contest]) -> pathlib.Path:
    # prepare params
    service = problem.get_service()

    for name in ('contest_id', 'contest_slug'):
        contest_id = getattr(problem, name, None)
        if contest_id:
            break
    else:
        contest_id = ''

    for name in ('problem_id', 'problem_slug', 'problem_no', 'task_id', 'task_slug', 'task_no', 'alphabet', 'index'):
        problem_id = getattr(problem, name, None)
        if problem_id:
            break
    else:
        problem_id, = urllib.parse.urlparse(problem.get_url()).path.lstrip('/').replace('/', '-'),

    params = {
        'service_name': service.get_name(),
        'service_domain': urllib.parse.urlparse(service.get_url()).netloc,
        'contest_id': contest_id,
        'problem_id': problem_id,
    }

    # generate the path
    problem_pattern = "{problem_id}" #config.get('problem_directory', '.')
    problem_directory = pathlib.Path(problem_pattern.format(**params)).expanduser()
    if contest is None:
        return problem_directory

    contest_pattern = "./Contests/{service_name}_{contest_id}"
    contest_directory = pathlib.Path(contest_pattern.format(**params)).expanduser()
    return contest_directory / problem_directory


def prepare_problem(problem: onlinejudge.type.Problem, *, contest: Optional[onlinejudge.type.Contest] = None, session: requests.Session) -> None:
    
    dir = get_directory(problem=problem, contest=contest)
    logger.info('use directory: %s', str(dir))

    dir.parent.mkdir(parents=True, exist_ok=True)
    with chdir(dir):
        url = problem.get_url()
        html = network.download_html(url, session=session)
        sample_cases = network.download_sample_cases(url, session=session)
        dest_str = "main.cpp"
        dest = pathlib.Path(dest_str)
        with open("../../../template/template.cpp") as codefile:
            code = codefile.read().encode('utf-8')
        # write
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            logger.error('file already exists: %s', str(dest))
        else:
            logger.info('write file: %s', str(dest))
            with open(dest, 'wb') as fh:
                fh.write(code)
            if code.startswith(b'#!'):
                os.chmod(dest, os.stat(dest).st_mode | stat.S_IEXEC)

        # download
        try:
            subprocess.check_call(['oj', 'download', problem.get_url()], stdout=sys.stdout, stderr=sys.stderr)
        except subprocess.CalledProcessError as e:
            logger.error('samples downloader failed: %s', e)


def prepare_contest(contest: onlinejudge.type.Contest, *, session: requests.Session) -> None:
    for i, problem in enumerate(contest.list_problems()):
        prepare_problem(problem, contest=contest, session=session)


default_config_path = pathlib.Path(appdirs.user_config_dir('online-judge-tools')) / 'prepare.config.toml'


def get_config(*, config_path: Optional[pathlib.Path] = None) -> Dict[str, Any]:
    config_path = config_path or default_config_path
    logger.info('config path: %s', str(config_path))
    if config_path.exists():
        return dict(**toml.load(config_path))
    else:
        return {}


def main(args: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('-c', '--cookie', default=onlinejudge.utils.default_cookie_path)
    parsed = parser.parse_args(args=args)

    # configure logging
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s%(levelname)s%(reset)s:%(name)s:%(message)s'))
    level = INFO
    basicConfig(level=level, handlers=[handler])

    with onlinejudge.utils.with_cookiejar(onlinejudge.utils.get_default_session(), path=parsed.cookie) as session:
        problem = onlinejudge.dispatch.problem_from_url(parsed.url)
        contest = onlinejudge.dispatch.contest_from_url(parsed.url)
        if problem is not None:
            prepare_problem(problem,session=session)
        elif contest is not None:
            prepare_contest(contest,session=session)
        else:
            raise ValueError(f"""unrecognized URL: {parsed.url}""")


if __name__ == '__main__':
    main()