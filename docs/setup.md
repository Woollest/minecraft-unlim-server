# セットアップ

## UbuntuノートPC

必要なもの：

- Docker EngineとDocker Compose
- Python 3.9以降
- OpenSSH Server
- Unlim CLI 1.5.80以降
- 稼働中または停止中のMinecraftコンテナ `minecraft`

Unlim CLIは公式手順で導入します。

```text
curl -fsSL https://unlim.cc/setup.sh | sh
```

管理エージェントを配置します。

```text
install -m 0755 server/wsm-agent.py ~/minecraft/wsm-agent
mkdir -p ~/.config/systemd/user
install -m 0644 server/unlim-daemon.service ~/.config/systemd/user/unlim-daemon.service
systemctl --user daemon-reload
systemctl --user enable --now unlim-daemon.service
```

ログインしていない状態でもユーザーサービスを動かすには、管理者権限でlingerを有効にします。

```text
sudo loginctl enable-linger "$USER"
```

## Windows管理端末

公開鍵認証でUbuntuへ接続できる状態にします。

```text
ssh woollest@wls-server.local
```

接続先のホスト鍵指紋は、ノートPC本体または信頼済みの既存接続と照合してから登録してください。

`manager/`からアプリをビルドするか、Releasesで配布されるインストーラーを使用します。

## 参加者のWindows端末

参加者は[Unlim公式手順](https://wiki.unlim.cc/getting-started)でWindows版CLIを導入し、`connector/` のアプリへ管理者から届いた招待キーを入力します。接続後はMinecraft Java版から `127.0.0.1:25565` へ参加します。

Connectorは招待キーを保存しません。また、Unlim本体はリポジトリやConnectorへ同梱せず、公式配布版を利用します。

## Java版専用化

現在の本番構成はTCP `25565` のみを公開します。以前使用していたGeyser/FloodgateとUDP `19132` は本番から外し、復旧可能な退避フォルダへ保存しています。

設定変更後は、Minecraftがhealthyになること、`plugins` の一覧にGeyser/Floodgateがないこと、ログに両プラグイン由来のエラーがないことを確認してから公開します。

## 運用上の注意

- Unlim接続キーはパスワードと同様に扱います。
- 管理GUIにSSH秘密鍵やMinecraft共通パスワードを埋め込まないでください。
- ワールド移行やプラグイン更新の前にバックアップと復元試験を行ってください。
- Unlim共有を停止すると、そのセッションのキーは無効になります。
