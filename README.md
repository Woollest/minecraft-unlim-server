# Minecraft Unlim Server

Dockerで動作するMinecraft Java Editionサーバーを、別のWindows端末からSSH経由で管理するためのプロジェクトです。参加者との接続には[Unlim](https://unlim.cc/)を使用するため、一般的なルーターのポート開放を行わずにサーバーを公開できます。

ホストはノートPCに限定されません。Dockerを実行できるLinuxサーバー、デスクトップPC、小型PC、VPSなどで利用できます。

## 構成

```text
参加者のWindows端末
└─ Participant Connector
        │ Unlim P2P
        ▼
Linuxホスト
├─ Docker Minecraft Paper :25565
├─ Unlim CLI / Agent Kit
├─ 管理エージェント
└─ バックアップ
        ▲
        │ SSH
Windows管理端末
└─ Server Manager
```

## ディレクトリ

- `manager/` — Tauri 2、React、TypeScript製のWindows管理GUI
- `server/` — Linuxホスト用の許可リスト方式管理エージェントとUnlimサービス
- `connector/` — 招待キーから接続する参加者用Windowsアプリ
- `docs/` — 導入・運用手順

## 管理GUIの機能

- Minecraftの稼働状態とヘルスチェック
- 起動、安全な停止、再起動
- オンラインプレイヤーと最新ログの確認
- 手動バックアップ
- TPS、ディスク容量、自動起動設定の確認
- UnlimによるTCP `25565` 共有の開始・停止
- Unlim招待情報の表示
- SSH接続先の設定
- ネットワーク、温度、メモリ、ディスク、バッテリー監視
- バックアップ一覧と最新バックアップへの安全な復元
- バックアップ・healthy確認・失敗時復旧を含む安全更新
- Discord Webhookによる障害通知とUnlim招待キーの自動共有

## 自動保守

`wsm-ops.timer` が5分ごとに状態を確認します。

- 24時間経過後、参加者がいないタイミングでバックアップ
- バックアップを最大5世代に整理
- ネットワーク復旧後にUnlim共有を再開
- 自動起動が有効なMinecraftだけを異常停止時に復旧
- ディスク、温度、メモリ、CPU負荷、バッテリー残量を監視
- 低バッテリー時にワールドを保存してMinecraftを安全停止
- Discord Webhook設定時に障害と復旧を通知

## 参加者用Connector

参加者はUnlim公式CLIを導入し、管理者から受け取った招待キーをConnectorへ入力します。標準構成では、接続後にMinecraft Java版から `127.0.0.1:25565` を指定します。

Connectorは招待キーを永続保存しません。Unlim本体もこのリポジトリには含まれないため、公式配布版を使用してください。

Powered by [Unlim](https://unlim.cc/)

## 必要環境

### Linuxホスト

- Docker EngineおよびDocker Compose
- Python 3.9以降
- OpenSSH Server
- Unlim CLI
- `minecraft` という名前のMinecraftコンテナ

### Windows管理端末

- Windows 10または11
- Linuxホストへ公開鍵認証で接続できるOpenSSHクライアント

環境固有のユーザー名、ホスト名、SSH鍵、Minecraftの保存先は、利用する環境に合わせて設定してください。

## セキュリティ

- Unlim API、Docker API、RCONを外部ネットワークへ直接公開しません。
- 管理操作はSSH経由で行います。
- Linux側の管理エージェントが受け付ける操作は許可リストで制限されています。
- Unlimキー、APIトークン、Minecraftの認証情報、SSH秘密鍵、ワールド、バックアップ、ログをリポジトリへ保存しないでください。
- 初回SSH接続時は、表示されたホスト鍵指紋をサーバー側で確認してください。

## 開発

管理GUIまたはConnectorのビルドには、Node.js、Rust、Tauri 2のWindows開発要件が必要です。

```text
cd manager
npm install
npm run tauri dev
```

配布用ビルド：

```text
npm run tauri build
```

詳細は[セットアップ手順](docs/setup.md)を参照してください。

## ライセンス

ライセンスは未指定です。明示的な許可なく再配布・改変利用はできません。
