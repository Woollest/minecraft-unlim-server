# セットアップ

以下の `<user>`、`<server-host>`、`<minecraft-dir>` は、実際の環境に合わせて置き換えてください。

## Linuxホスト

必要なもの：

- Docker EngineとDocker Compose
- Python 3.9以降
- OpenSSH Server
- Unlim CLI
- 稼働中または停止中のMinecraftコンテナ `minecraft`

Linuxホストは、ノートPC、デスクトップPC、専用サーバー、VPSなど任意の形態で構いません。

Unlim CLIは[公式手順](https://wiki.unlim.cc/getting-started)に従って導入します。

管理エージェントとユーザーサービスを配置します。次の例ではMinecraftの管理ディレクトリを `~/minecraft` としています。

```text
install -m 0755 server/wsm-agent.py ~/minecraft/wsm-agent
install -m 0755 server/wsm-ops.py ~/minecraft/wsm-ops
mkdir -p ~/.config/systemd/user
install -m 0644 server/unlim-daemon.service ~/.config/systemd/user/unlim-daemon.service
install -m 0644 server/wsm-ops.service server/wsm-ops.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now unlim-daemon.service
systemctl --user enable --now wsm-ops.timer
```

別のディレクトリを使用する場合は、管理エージェントとサービスファイル内のパスも変更してください。

ログインしていない状態でもユーザーサービスを動かす場合は、管理者権限でlingerを有効にします。

```text
sudo loginctl enable-linger "<user>"
```

## Windows管理端末

公開鍵認証でLinuxホストへ接続できる状態にします。

```text
ssh <user>@<server-host>
```

初回接続時に表示されるホスト鍵指紋は、Linuxホスト本体または信頼できる別経路で照合してください。

`manager/` からアプリをビルドするか、Releasesで配布されるインストーラーを使用します。別の環境向けにビルドする場合は、`manager/src-tauri/src/lib.rs` のSSH接続先、ユーザー名、管理エージェントのパスを変更してください。

現在の管理GUIでは「接続設定」からホスト名、予備IP、SSHユーザー、管理エージェントのパスを変更できます。設定はWindowsユーザーのAppDataへ保存され、SSH秘密鍵は保存しません。

## 自動保守と通知

初回実行時に `~/.config/wsm/ops.json` が権限600で作成されます。監視間隔は5分、バックアップ間隔は24時間、保存数は5世代です。参加者がオンラインの場合、バックアップと更新は延期されます。

Discord通知を使う場合は、Discordで通知用チャンネルのWebhook URLを作成し、管理GUIの「Discord」から登録します。URLはLinuxホストだけに保存され、リポジトリには含まれません。空欄を保存すると通知を無効化できます。

## 参加者のWindows端末

参加者は[Unlim公式手順](https://wiki.unlim.cc/getting-started)でWindows版CLIを導入し、`connector/` のアプリへ管理者から届いた招待キーを入力します。

標準のMinecraftポートを共有している場合、接続先は次のとおりです。

```text
127.0.0.1:25565
```

ローカルの `25565` がほかのアプリで使用されている場合は、Unlimが表示する実際のローカルポートを使用してください。Connectorは招待キーを永続保存せず、Unlim本体も同梱しません。

## Minecraft構成

標準構成はMinecraft Java Edition用のTCP `25565` を共有します。統合版にも対応させる場合は、Geyser/Floodgateの導入とUDPポートの追加設定が別途必要です。

設定変更後は、次の項目を確認してから公開してください。

- コンテナがhealthyになること
- 必要なプラグインがすべて読み込まれていること
- 起動ログに重大なエラーがないこと
- バックアップから復元できること

## 運用上の注意

- Unlim接続キーはパスワードと同様に扱ってください。
- 管理GUIへSSH秘密鍵やMinecraftの認証情報を埋め込まないでください。
- ワールド移行やプラグイン更新の前にバックアップと復元試験を行ってください。
- Unlim共有を停止すると、そのセッションの招待キーは無効になります。
