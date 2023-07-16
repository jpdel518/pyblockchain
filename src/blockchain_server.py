from flask import Flask
from flask import jsonify
from flask import request

import blockchain
import wallet

app = Flask(__name__)

cache = {}


def get_blockchain():
    # FIXME 本来であればDBに保存するが簡易的にcacheに保存する
    cached_blockchain = cache.get('blockchain')
    if not cached_blockchain:
        miners_wallet = wallet.Wallet()
        cache['blockchain'] = blockchain.BlockChain(
            blockchain_address=miners_wallet.blockchain_address,
            port=app.config['port']
        )
        # マイナスを許可しないのであれば、マイニングによって得られる仮想通貨が最初の仮想通貨になる
        # つまりwalletのUIに下記の情報を入れて、取引を行うことでマイナスを許可しない仮想通貨取引が行えるようになる
        app.logger.warning({
            'private_key': miners_wallet.private_key,
            'public_key': miners_wallet.public_key,
            'blockchain_address': miners_wallet.blockchain_address,
        })
    return cache['blockchain']


@app.route('/chain', methods=['GET'])
def get_chain():
    block_chain = get_blockchain()
    response = {
        'chain': block_chain.chain
    }
    # jsonでレスポンス返す時にjsonify使用
    return jsonify(response), 200


@app.route('/transactions', methods=['GET', 'POST', 'PUT', 'DELETE'])
def transaction():
    block_chain = get_blockchain()
    if request.method == 'GET':
        # トランザクションプール情報を取得
        transactions = block_chain.transaction_pool
        response = {
            'transactions': transactions,
            'length': len(transactions)
        }
        return jsonify(response), 200

    if request.method == 'POST':
        # トランザクションの作成
        request_json = request.json
        required = {
            'sender_blockchain_address',
            'recipient_blockchain_address',
            'value',
            'sender_public_key',
            'signature',
        }
        # requestのキーがrequiredに入っているか
        # all()は全て引数に入る配列が全てTrueの場合にTrueを返す関数
        # for k in required ： requiredに入っている値の取り出し
        # k in request_json ： request_jsonのキー値にk（↑で取得したrequiredの値）が含まれているか
        if not all(k in request_json for k in required):
            return jsonify({'message': 'missing values'}), 400

        is_created = block_chain.create_transaction(
            request_json['sender_blockchain_address'],
            request_json['recipient_blockchain_address'],
            request_json['value'],
            request_json['sender_public_key'],
            request_json['signature'],
        )
        if not is_created:
            jsonify({'message': 'fail'}), 400

        return jsonify({'message': 'success'}), 201

    if request.method == 'PUT':
        # 他ノードでトランザクションが作成された際のトランザクションの同期
        # 送られてきた情報のvalue check
        request_json = request.json
        required = {
            'sender_blockchain_address',
            'recipient_blockchain_address',
            'value',
            'sender_public_key',
            'signature',
        }
        if not all(k in request_json for k in required):
            return jsonify({'message': 'missing values'}), 400

        # 送られてきた情報をトランザクションに追加
        is_added = block_chain.add_transaction(
            request_json['sender_blockchain_address'],
            request_json['recipient_blockchain_address'],
            request_json['value'],
            request_json['sender_public_key'],
            request_json['signature'],
        )
        if not is_added:
            jsonify({'message': 'fail'}), 400

        return jsonify({'message': 'success'}), 200

    if request.method == 'DELETE':
        # ブロックが作られたらプールを空にする形での同期
        block_chain.transaction_pool = []
        return jsonify({'message': 'success'}), 200

@app.route('/mine', methods=['GET']) # 本当はPOSTだけど簡易的に確認するためにGETを使用
def mine():
    block_chain = get_blockchain()
    is_mined = block_chain.mining()
    if is_mined:
        return jsonify({'message': 'success'}), 200
    return jsonify({'message': 'fail'}), 400

@app.route('/mine/start', methods=['GET']) # 本来であればmainで実行すべきだが、学習理解しやすいようにAPI化
def start_mine():
    block_chain = get_blockchain()
    block_chain.start_mining()
    return jsonify({'message': 'start mining'}), 200

@app.route('/consensus', methods=['PUT'])
def consensus():
    blockchain = get_blockchain()
    replaced = blockchain.resolve_conflicts()
    return jsonify({'replaced': replaced}), 200

@app.route('/amount', methods=["GET"])
def get_total_amount():
    # 保持している仮想通貨の合計金額を計算
    # getパラメーターからアドレスを取得
    blockchain_address = request.args['blockchain_address']
    return jsonify({
        'amount': get_blockchain().calculate_total_amount(blockchain_address)
    }), 200

if __name__ == '__main__':
    # ArgumentParserはPythonの実行時にコマンドライン引数を取りたいときに使用
    from argparse import ArgumentParser

    parser = ArgumentParser()
    # -p, --portでint型のコマンドライン引数を受け取るよってこと
    parser.add_argument('-p', '--port', default=5050, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.config['port'] = port

    get_blockchain().run()

    # 0.0.0.0 = localhost
    # threadedは同時リクエストを受け付けるオプション（本番環境ではapacheやnginxがflaskの前にいてスレッド処理してくれるけど、なくてもflask自体がスレッド処理してくれるようにできる）
    app.run(host='0.0.0.0', port=port, threaded=True, debug=True)
