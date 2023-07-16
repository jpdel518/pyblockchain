import binascii

import base58
import codecs
import hashlib

from ecdsa import NIST256p
from ecdsa import SigningKey

import utils


class Wallet(object):

    def __init__(self):
        # ECDSA(楕円曲線暗号)の曲線をNIST256pで鍵を作成
        self._private_key = SigningKey.generate(curve=NIST256p)
        self._public_key = self._private_key.get_verifying_key()
        self._blockchain_address = self.generate_blockchain_address()

    @property
    def private_key(self):
        return self._private_key.to_string().hex()

    @property
    def public_key(self):
        return self._public_key.to_string().hex()

    @property
    def blockchain_address(self):
        return self._blockchain_address

    def generate_blockchain_address(self):
        """
        publicKeyはデータサイズが大きいので、walletのアドレスはpublicKeyからユニークな値を生成して使用する
        ビットコインと同じアルゴリズムでとりあえず作成
        TODO アルゴリズムは考慮し直す余地あり
        """
        # ステップ1
        # publicKeyのバイト配列を取得
        public_key_bytes = self._public_key.to_string()

        # ステップ2
        # バイナリパブリックキーから作成したSha256オブジェクトを取得
        sha256_bpk = hashlib.sha256(public_key_bytes)
        # Sha256ハッシュ値を取得
        sha256_bpk_digest = sha256_bpk.digest()

        # ステップ３
        # Ripemd160(Shaよりも短いハッシュを生成できる)を使用
        ripemd160_bpk = hashlib.new('ripemd160')
        ripemd160_bpk.update(sha256_bpk_digest)
        # Ripemd160ハッシュ値を取得
        ripemd160_bpk_digest = ripemd160_bpk.digest()
        # バイト配列からhexにエンコード
        ripemd160_bpk_hex = codecs.encode(ripemd160_bpk_digest, 'hex')

        # ステップ４
        # ネットワークバイトを追加
        network_byte = b'00'
        network_bitcoin_public_key = network_byte + ripemd160_bpk_hex
        # hexからバイト配列にデコード
        network_bitcoin_public_key_bytes = codecs.decode(network_bitcoin_public_key, 'hex')

        # ステップ５
        # SHA256を使用したダブルハッシュ（1/2）
        sha256_bpk = hashlib.sha256(network_bitcoin_public_key_bytes)
        # ハッシュ値を取得
        sha256_bpk_digest = sha256_bpk.digest()
        # SHA256を使用したダブルハッシュ（2/2）
        sha256_2_nbpk = hashlib.sha256(sha256_bpk_digest)
        # ダブルハッシュしたハッシュ値を取得
        sha256_2_nbpk_digest = sha256_2_nbpk.digest()
        # バイト配列からhexにエンコード
        sha256_hex = codecs.encode(sha256_2_nbpk_digest, 'hex')

        # ステップ６
        # チェックサムの取得
        # hexの先頭から8つチェックサムとして使用
        checksum = sha256_hex[:8]

        # ステップ７
        # publicKeyにチェックサムを付与してデータの信頼性を確かめるために使用
        address_hex = (network_bitcoin_public_key + checksum).decode('utf-8')

        # ステップ８
        # base58でエンコード
        blockchain_address = base58.b58encode(binascii.unhexlify(address_hex)).decode('utf-8')
        return blockchain_address


class Transaction(object):
    def __init__(self, sender_private_key, sender_public_key, sender_blockchain_address,
                 recipient_blockchain_address, value):
        self.sender_private_key = sender_private_key
        self.sender_public_key = sender_public_key
        self.sender_blockchain_address = sender_blockchain_address
        self.recipient_blockchain_address = recipient_blockchain_address
        self.value = value

    def generate_signature(self):
        sha256 = hashlib.sha256()
        # 相手に送信するトランザクションをprivateKeyで署名する
        transaction = utils.sort_dict_by_key({
            'sender_blockchain_address': self.sender_blockchain_address,
            'recipient_blockchain_address': self.recipient_blockchain_address,
            'value': float(self.value)
        })
        sha256.update(str(transaction).encode('utf-8'))
        message = sha256.digest()
        # walletのprivateKeyを復元
        private_key = SigningKey.from_string(
            bytes().fromhex(self.sender_private_key), curve=NIST256p
        )
        signed_message = private_key.sign(message)
        signature = signed_message.hex()
        return signature





if __name__ == '__main__':
    wallet = Wallet()
    # privateKeyの確認
    print('check privateKey', wallet.private_key)
    # publicKeyの確認
    print('check publicKey', wallet.public_key)
    # blockchainAddressの確認
    print('check blockchain_address', wallet.blockchain_address)

    # walletからwallet_Bに送金する流れ！！！！！！
    wallet_B = Wallet()
    wallet_Mining = Wallet()

    # 1. まずwalletからwallet_Bに送金するトランザクションをwalletのサーバー上で作成
    transaction = Transaction(wallet.private_key, wallet.public_key, wallet.blockchain_address, wallet_B.blockchain_address, 2.0)
    # 署名の確認
    print('check signature', transaction.generate_signature())

    # 2. BlockChainのノードに投げる（本来であればREST等で実行）
    import blockchain
    block_chain = blockchain.BlockChain(wallet_Mining.blockchain_address)
    # 3. BlockChainノード上で取引開始
    # 4. 受信した情報からトランザクションを作成、publicキーを用いて受信したトランザクションの署名と作成したトランザクションが同じものか検証
    # 5. 同じもの（トランザクション情報の書き換えが起きていないこと）が確認できたらトランザクションプールに本取引のトランザクションを追加
    is_added = block_chain.add_transaction(
        wallet.blockchain_address,
        wallet_B.blockchain_address,
        2.0,
        wallet.public_key,
        transaction.generate_signature(),
    )
    print('ADDED?', is_added)
    if is_added:
        # 6. 送金を実行するためのマイニング開始
        # 7. マイニングではマイニング報酬受け取り用のトランザクションをトランザクションプールに追加
        # 8. 次にproof_of_work（マイニング難易度を満たすハッシュを作り出すことができるnonceを見つける）を実行
        # 9. nonceが見つかったら処理するトランザクションとnonce, timestamp等をまとめた「Block」を作成する
        # 10. BlockをChainにappendする = 記帳される = 送金完了
        block_chain.mining()
    utils.pprint(block_chain.chain)
    # 送金結果
    print('A', block_chain.calculate_total_amount(wallet.blockchain_address))
    print('B', block_chain.calculate_total_amount(wallet_B.blockchain_address))
    print('Mining', block_chain.calculate_total_amount(wallet_Mining.blockchain_address))
