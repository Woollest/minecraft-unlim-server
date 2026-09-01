# Woollest SMP Connector

参加者がUnlimの招待キーだけでWoollest SMPへ接続するためのWindowsアプリです。

## 使い方

1. Connectorを起動します。必要なUnlim公式版は自動的に導入・更新されます。
2. 管理者から届いた招待キーをConnectorへ貼り付けて「接続する」を押します。
3. Minecraft Java版で `127.0.0.1:25565` へ接続します。

最後に接続した招待キーはWindows資格情報へ安全に保存し、次回起動時に自動入力します。保存したキーはアプリ内から削除できます。Unlimは公式配布APIのURLから取得し、公開されているファイルサイズとSHA-256が一致した場合だけ使用します。Connector自身の更新も署名検証後に適用します。Unlimが同じポートを使用できない場合は、Unlim側に表示される実際のローカルポートを確認してください。

Connectorは起動済みのUnlimを検出して再利用し、複数インスタンスが存在する場合も接続状態と実際のローカルポートを判定します。

Powered by [Unlim](https://unlim.cc/)
