import contextlib
import logging
import sys
import time
import hashlib
import json
import threading
import requests

from ecdsa import NIST256p
from ecdsa import VerifyingKey

import utils



# マイニングの難易度
# challenge + previous_hash + transactionの値の先頭が0 * MINING_DIFFICULTYになるようなnonceを探す
# 例えば、MINING_DIFFICULTY=3の場合、先頭が000になるようなnonceを探す
# 大体10minくらいで見つかる値が良いらしい
# このnonceを探す処理のことを「マイニング」という
MINING_DIFFICULTY = 3
# マイニングの報酬を送る人
MINING_SENDER = 'THE BLOCKCHAIN'
# マイニング報酬
MINING_REWARD = 1.0
# マイニングの実行間隔
MINING_TIMER_SEC = 20

# utils.pyのfind_neighborsを使って探索する範囲を指定
BLOCKCHAIN_PORT_RANGE = (5050, 5051)
NEIGHBORS_IP_RANGE = (-2, 2)
BLOCKCHAIN_NEIGHBORS_SYNC_TIME_SEC = 20


logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

class BlockChain(object):
    def __init__(self, blockchain_address=None, port=None):
        self.transaction_pool = []
        self.chain = []
        self.neighbors = []
        # 最初のブロックを作成
        self.create_block(0, self.hash({}))
        self.blockchain_address = blockchain_address
        self.port = port
        self.mining_semaphore = threading.Semaphore(1)
        self.sync_neighbors_semaphore = threading.Semaphore(1)

    def run(self):
        # ブロックチェーンサーバー起動時に実行する処理
        # ノードを自動探索
        self.sync_neighbors()
        # chainの同期
        # すでに他ノードに100件とか複数件のchainが作成されている状態で、新しくノード追加された場合を考慮
        self.resolve_conflicts()
        # TODO 自動マイニング（デバッグしやすいように手動マイニングできるようにしている）
        # self.start_mining()

    def set_neighbors(self):
        # ブロックチェーンノードの探索
        self.neighbors = utils.find_neighbors(
            utils.get_host(),
            self.port,
            NEIGHBORS_IP_RANGE[0],
            NEIGHBORS_IP_RANGE[1],
            BLOCKCHAIN_PORT_RANGE[0],
            BLOCKCHAIN_PORT_RANGE[1]
        )
        logger.info({
            "action": "set_neighbors",
            "neighbors": self.neighbors,
        })

    def sync_neighbors(self):
        # ブロックチェーンノードの自動探索（同期）
        is_acquired = self.sync_neighbors_semaphore.acquire(blocking=False)
        if is_acquired:
            with contextlib.ExitStack() as stack:
                stack.callback(self.sync_neighbors_semaphore.release)
                self.set_neighbors()
                loop = threading.Timer(BLOCKCHAIN_NEIGHBORS_SYNC_TIME_SEC, self.sync_neighbors)
                loop.start()

    def create_block(self, nonce, previous_hash):
        # Creates a new Block and adds it to the chain
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': self.transaction_pool,
            'nonce': nonce,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        block = utils.sort_dict_by_key(block)
        self.chain.append(block)
        self.transaction_pool = []

        # 他のノードにsync
        for node in self.neighbors:
            requests.delete(
                f'http://{node}/transactions'
            )

        return block

    def add_transaction(self, sender_blockchain_address, recipient_blockchain_address, value, sender_public_key=None, signature=None):
        # Adds a new transaction to the list of transactions
        transaction = utils.sort_dict_by_key({
            'sender_blockchain_address': sender_blockchain_address,
            'recipient_blockchain_address': recipient_blockchain_address,
            'value': float(value), # bitcoinは小数点以下を扱う
        })

        # マイニングの場合はユーザー間の送信ではないのでverificationは必要ない
        if sender_blockchain_address == MINING_SENDER:
            self.transaction_pool.append(transaction)
            return True

        # TODO デバッグ用にマイナスを許可している状態。コメントを外す必要あり
        # もし送信者の残高が足りない場合は失敗
        # if self.calculate_total_amount(sender_blockchain_address) < float(value):
        #     logger.error({'action': 'addTransaction', 'error': 'not enough balance'})
        #     return False

        # ユーザー間の送受信の場合はverificationが必要
        if self.verify_transaction(sender_public_key, signature, transaction):
            self.transaction_pool.append(transaction)
            return True

        return False

    def create_transaction(self, sender_blockchain_address, recipient_blockchain_address, value, sender_public_key, signature):
        is_transacted = self.add_transaction(
            sender_blockchain_address, recipient_blockchain_address, value, sender_public_key, signature)

        # 他のノードにSyncさせる
        if is_transacted:
            for node in self.neighbors:
                requests.put(
                    f'http://{node}/transactions',
                    json={
                        'sender_blockchain_address': sender_blockchain_address,
                        'recipient_blockchain_address': recipient_blockchain_address,
                        'value': value,
                        'sender_public_key': sender_public_key,
                        'signature': signature,
                    }
                )

        return is_transacted

    def verify_transaction(self, sender_public_key, signature, transaction):
        # 比較するためのハッシュ値を取得
        sha256 = hashlib.sha256()
        sha256.update(str(transaction).encode('utf-8'))
        message = sha256.digest()
        # 署名をpublicKeyで元に戻して比較
        # signatureはバイト配列で渡す必要がある
        signature_bytes = bytes().fromhex(signature)
        verifying_key = VerifyingKey.from_string(
            bytes().fromhex(sender_public_key), curve=NIST256p
        )
        # transactionの書き換えが起きていないことを検証（異なると判定されるとBadSignatureErrorが発生）
        verified = verifying_key.verify(signature_bytes, message)
        return verified

    def hash(self, block):
        # Hashes a Block
        # json.dumpsでstringに変換する際に、ソートすることで順番が入れ替わってハッシュ値が異なることを防ぐ
        # 事前にcreate_blockでソートしているが、hashメソッドを呼び出す処理があるかもしれないので、、、＋ ダブルチェックの意も込めて
        sorted_block = json.dumps(block, sort_keys=True)
        # sha256でハッシュ値を計算
        return hashlib.sha256(sorted_block.encode()).hexdigest()

    def proof_of_work(self):
        """
        コンセンサスアルゴリズムでnonceを探すことをproof of workという:
        - Find a number nonce such that hash(challenge(candidate of nonce) + previous_hash + transaction) contains leading 3 zeroes
        - 3 is lead from the number of difficulty
        :return: <int>
        """

        logger.info('Searching for next proof')
        transactions = self.transaction_pool.copy()
        previous_hash = self.hash(self.chain[-1])
        nonce = 0
        # transactions, previous_hash, nonceから作成されるhash値の先頭difficultyの数分
        # 0が続くようなnonceを見つける（マイニングの難易度を満たすnonceを探す） = コンセンサスアルゴリズム
        while self.valid_proof(transactions, previous_hash, nonce) is False:
            nonce += 1

        logger.info('Found proof: %s', nonce)
        return nonce

    def valid_proof(self, transactions, previous_hash, nonce, difficulty=MINING_DIFFICULTY):
        """
        Validates the Proof: Does hash(transactions, previous_hash, nonce) contain number of difficulty leading zeroes?
        :param transactions: <dictionary> whole transactions
        :param previous_hash: <string> previous hash
        :param nonce: <int> challenge
        :return: <bool> True if correct, False if not.
        """

        guess = utils.sort_dict_by_key({
            'transactions': transactions,
            'previous_hash': previous_hash,
            'nonce': nonce,
        })
        guess_hash = self.hash(guess)
        # difficultyのバイト数だけ先頭が0になっているかチェック
        return guess_hash[:difficulty] == '0' * difficulty

    def mining(self):
        # 空の場合でもマイニングしないと誰も仮想通貨を持っていない状態になってしまうので、トランザクションプールが空の場合も許可
        # # トランザクションプールが空の場合はマイニングしない
        # # 実際のBitcoinでは空でも実行するが、この環境では空のminingを実行してMINING_REWARDがどんどん追加されるとログが見辛くなるため
        # if not self.transaction_pool:
        #     logger.error({'action': 'mining', 'error': 'there is no transaction'})
        #     return False

        # マイニング報酬を送る
        self.add_transaction(
            sender_blockchain_address=MINING_SENDER,
            recipient_blockchain_address=self.blockchain_address,
            value=MINING_REWARD,
        )
        # マイニング
        previous_hash = self.hash(self.chain[-1])
        nonce = self.proof_of_work()
        self.create_block(nonce, previous_hash)
        logger.info({'action': 'mining', 'status': 'success'})

        # SYNC
        for node in self.neighbors:
            requests.put(f'http://{node}/consensus')

        return True

    def start_mining(self):
        # マイニングを定期的に実行するメソッド
        # blockingをTrueにすると、他のスレッドがマイニングを終えるまで待つ（キュー状）
        is_acquired = self.mining_semaphore.acquire(blocking=False)
        if is_acquired:
            with contextlib.ExitStack() as stack:
                # マイニングを終えたら、セマフォを解放する（miningでexception等が起きても必ず実行）
                stack.callback(self.mining_semaphore.release)
                self.mining()
                # 終了後に再度start_miningを呼び出す
                # ただし、このサービスではdifficultyの数が0が3つなので、マイニングが終わるのが早すぎる（通常は10min程度かかるようなdifficultyが設定されているが、数秒で終了する）
                # そのため、擬似的にTimerを使って、20秒後に再度マイニングを呼び出す
                loop = threading.Timer(MINING_TIMER_SEC, self.start_mining)
                loop.start()


    def calculate_total_amount(self, blockchain_address):
        # ブロックチェーンの合計金額を計算
        total_amount = 0.0
        for block in self.chain:
            for transaction in block['transactions']:
                if transaction['sender_blockchain_address'] == blockchain_address:
                    total_amount -= float(transaction['value'])
                if transaction['recipient_blockchain_address'] == blockchain_address:
                    total_amount += float(transaction['value'])
        return total_amount

    def valid_chain(self, chain):
        # コンセンサス
        # ブロックチェーンの各ブロックとその繋がりが正しいか検証する
        pre_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            # 1つ前のブロックを使ったハッシュ値であることを検証
            if block['previous_hash'] != self.hash(pre_block):
                return False
            # nonceが正しい数値かを検証（proof_of_workで作成されるnonceであれば通過できるはず）
            if not self.valid_proof(block['transactions'], block['previous_hash'], block['nonce']):
                return False

            pre_block = block
            current_index += 1
        return True

    def resolve_conflicts(self):
        # リゾルブコンフリクト
        # 最も長いchainを採用するとする（これが一般的なルールだが、ここは各BlockChainで変えても良い）
        longest_chain = None
        max_length = len(self.chain)
        for node in self.neighbors:
            response = requests.get(f'http://{node}/chain')
            response_json = response.json()
            chain = response_json['chain']
            chain_length = len(chain)
            # 別ノードから取得したchainのなかで最大長かつ、正しいnonceが設定されたものlongest_chainにいれる
            if chain_length > max_length and self.valid_chain(chain):
                max_length = chain_length
                longest_chain = chain

        # もしlongest_chainが空じゃなかったら自身の保持するchainを置き換える
        if longest_chain:
            self.chain = longest_chain
            logger.info({"action": "resolve_conflicts", "status": "replaced"})
            return True

        logger.info({"action": "resolve_conflicts", "status": "not replaced"})
        return False


# スクリプト直接実行されたら呼ばれる
if __name__ == '__main__':
    my_blockchain_address = 'my_blockchain_address'
    # ブロックチェーンを作成
    blockchain = BlockChain(blockchain_address=my_blockchain_address)
    # ブロックチェーンを表示
    utils.pprint(blockchain.chain)

    # トランザクションを追加（送金デモ：AさんからBさんへ1.0のブロックチェーンを送金）
    blockchain.add_transaction('A', 'B', 1.0)
    blockchain.mining()
    utils.pprint(blockchain.chain)

    # トランザクションを追加（送金デモ：CさんからDさんへ2.0のブロックチェーンを送金）
    blockchain.add_transaction('C', 'D', 2.0)
    blockchain.mining()
    utils.pprint(blockchain.chain)

    print('私の残高: %s' % blockchain.calculate_total_amount(my_blockchain_address))
    print('Aさんの残高: %s' % blockchain.calculate_total_amount('A'))
    print('Bさんの残高: %s' % blockchain.calculate_total_amount('B'))
