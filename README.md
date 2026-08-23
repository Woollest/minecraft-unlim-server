# Minecraft Unlim Server

Minecraft Java EditionサーバーをUbuntuノートPCで常時運用し、Windowsデスクトップから安全に管理するためのプロジェクトです。参加者の接続には[Unlim](https://unlim.cc/)を使用します。

## 構成

```text
参加者用Connector
        │ Unlim P2P
        ▼
UbuntuノートPC
├─ Docker Minecraft Paper :25565
├─ Unlim CLI / Agent Kit
├─ wsm-agent
└─ 自動バックアップ
        ▲
        │ SSH
Windowsデスクトップ
└─ Woollest Server Manager
```

## ディレクトリ

- `manager/` — Tauri 2 + React + TypeScript製のWindows管理GUI
- `server/` — Ubuntu側の許可リスト方式管理エージェントとUnlimサービス
- `docs/` — 導入・運用手順
- `connector/` — 招待キーだけで接続できる参加者用Windowsアプリ

## 参加者用Connector

参加者はUnlim公式CLIを導入し、Connectorへ招待キーを貼り付けます。接続後、Minecraft Java版から `127.0.0.1:25565` を指定します。Connectorは招待キーを保存しません。

Powered by [Unlim](https://unlim.cc/)

## 管理GUIの機能

- Minecraftの状態・healthy確認
- 起動、安全な停止、再起動
- 参加者一覧と最新ログ
- 手動バックアップ
- TPS、ディスク容量、自動起動状態
- Unlim `25565/TCP`共有の開始・停止
- Unlim招待情報の表示

## セキュリティ

- Unlim API、Docker API、RCONをネットワークへ公開しません。
- Windows管理GUIからUbuntuへの操作はSSH経由です。
- Ubuntu側エージェントが受け付ける操作は許可リストで制限されています。
- Unlimキー、APIトークン、共通パスワード、SSH秘密鍵、ワールド、バックアップ、ログはリポジトリへ保存しません。

## 開発

管理GUIにはNode.js、Rust、Tauri 2のWindows開発要件が必要です。

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
