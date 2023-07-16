## Dockerの起動
```shell
docker network create net1  
docker-compose up -d --build
```

### 複数コンテナの立ち上げ
#### ループバックアドレスの登録
```shell
sudo ifconfig lo0 alias <IPアドレス>  
例：sudo ifconfig lo0 alias 127.0.0.2
```

```shell
.evnのIPに<IPアドレス>を設定
例: IP=127.0.0.2
```

#### コンテナを別名をつけて立ち上げ（対象のコンテナを操作する際には、p）
```shell
docker-compose -p <compose名> up -d build  
例：docker-compose -p other up -d build
```

## サービス操作方法
### Wallet画面の起動
http://<envに書かれたIPアドレス>:8080
例：http://127.0.0.1:8080

### Wallet画面での操作
- 送金(Transaction作成)  
SendMoneyのAddressに送金先のアドレスを入力し、Amountに送金額を入力してSendボタンを押下する。

### Transaction（送金処理）
- Transactionの確認  
http://<envに書かれたIPアドレス>:5050/transactions
- BlockChainの確認  
http://<envに書かれたIPアドレス>:5050/chain
- 手動マイニングの実行  
http://<envに書かれたIPアドレス>:5050/mine
- 自動マイニングの実行  
http://<envに書かれたIPアドレス>:5050/mine/start

## Dockerの中に入って直接pythonファイルをmain実行する方法
- utils.pyを実行
```shell
docker-compose exec -it blockchain sh
python utils.py
```
- 新しいWalletをポート番号5051で立ち上げたい場合
```shell
docker-compose exec -it blockchain sh
python wallet_server.py -p 5051
```

## Dockerの停止
```shell
docker-compose down
docker network rm net1
```

## 51%攻撃とは
```text
悪意のあるグループがネットワーク全体のマイニング速度の51%を支配して不正な取引を行うこと。
例えば取引所に100BTCを送金。
さらに自分（自分の異なるアカウント）に対して100BTCを送る。
自分に送った方は隠してしまう。隠した状態でブロックをマイニングし続けてチェーンを伸ばしていく。
隠された状態では取引所に送金したブロックのチェーンが最も長いので採用される。
その状態で別のコインに変えて他の取引所に細かく送金を行い自分のものとする。
この時に別コインに変えただけなので、取引所には100BTCがある。
その瞬間に隠していたチェーンを公開する。
公開されたチェーンは51%のマイニング速度を保持しているので、取引所に送金したチェーンよりも長いチェーンである。
そのため、隠されていたチェーンの方が正しいとなって、取引所に送金したチェーンは破棄される。
つまり取引所が保持している100BTCは消えて、大損害を被る。
```
