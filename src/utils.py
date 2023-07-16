import collections
import logging
import re
import socket

logger = logging.getLogger(__name__)

RE_IP = re.compile('(?P<first_ip>^\\d{1,3})\\.(?P<second_ip>\\d{1,3})\\.(?P<third_ip>\\d{1,3})\\.(?P<last_ip>\\d{1,3}$)')


def pprint(chains):
    for i, chain in enumerate(chains):
        print(f"{'=' * 25} Chain {i} {'=' * 25}")
        for k, v in chain.items():
            if k == 'transactions':
                print(k)
                for d in v:
                    print(f"{'-' * 40}")
                    for kk, vv in d.items():
                        print(f"  {kk:30}{vv}")
            else:
                print(f"{k:15}{v}")
    print(f"{'*' * 25}")


def sort_dict_by_key(unsorted_dict):
    # dictionaryの順番が異なるとハッシュ値が異なる。
    # そのため、dictionaryをソートしてからハッシュ値を計算する。lambda d:d[0]は、keyでソートすることを指定している。（python3ではlambda d:d[0]なくてもいいらしい）
    return collections.OrderedDict(sorted(unsorted_dict.items(), key=lambda d: d[0]))


def is_found_host(target, port):
    # target: 探したいホスト
    # port: 探したいポート
    # ホストとポートを指定してノードを見つけるメソッド

    # socket.AF_INETはIPv4を表す
    # socket.SOCK_STREAMはTCP/IPを表す
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        try:
            sock.connect((target, port))
            return True
        except Exception as ex:
            logger.error({
                'action': 'is_found_host',
                'target': target,
                'port': port,
                'error': ex,
            })
            return False

def get_host():
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception as ex:
        logger.error({
            "action": "get_host",
            "error": ex,
        })
        return "127.0.0.1"

def find_neighbors(my_host, my_port, start_ip_range, end_ip_range, start_port, end_port):
    # 範囲を指定して新しいノードを見つけるメソッド
    # 自分のhost, portを元にip range, port rangeを指定して、自分以外のノードを探す
    address = f'{my_host}:{my_port}'
    m = RE_IP.match(my_host)
    if not m:
        return None

    first_ip = m.group('first_ip')
    second_ip = m.group('second_ip')
    third_ip = m.group('third_ip')
    last_ip = m.group('last_ip')

    neighbors = []
    for guess_port in range(start_port, end_port):
        for ip_range in range(start_ip_range, end_ip_range):
            guess_host = f'{int(first_ip)}.{int(second_ip)}.{int(third_ip)}.{int(last_ip) + int(ip_range)}'
            guess_address = f'{guess_host}:{guess_port}'
            if guess_address == address:
                continue
            if is_found_host(guess_host, guess_port):
                neighbors.append(guess_address)
    return neighbors


if __name__ == '__main__':
    # print(is_found_host('127.0.0.1', 5050))
    # print(find_neighbors('127.0.0.1', 5050, 0, 3, 5050, 5051))
    print(get_host())
    print(is_found_host(get_host(), 5050))
    print(find_neighbors(get_host(), 5050, 0, 3, 5050, 5051))
