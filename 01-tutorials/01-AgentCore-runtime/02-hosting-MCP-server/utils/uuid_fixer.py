"""
UUIDフォーマットの問題を修正するためのユーティリティモジュール
"""

import json
import logging
import re
from typing import Any, Callable, ClassVar, Optional

# ロギングの設定
logger = logging.getLogger("agent_utils.uuid_fixer")


class UUIDFixer:
    """UUIDフォーマットの問題を修正するためのユーティリティクラス"""

    _original_validate_json: ClassVar[Optional[Callable]] = None

    @staticmethod
    def fix_uuid_format(content: Any) -> Any:
        """UUIDの形式を修正する(引用符で囲まれていないUUIDを引用符で囲む)"""
        text = content.decode("utf-8") if isinstance(content, bytes) else content

        # 詳細なログ出力
        logger.debug(f"修正前の生データ: {text[:500]!r}...")

        # 問題のある部分を特定するための正規表現パターン
        # 1. "id":UUID パターンを検出して修正（UUIDパターンのみ対象）
        pattern1 = r'"id":([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
        replacement1 = r'"id":"\1"'
        fixed_text = re.sub(pattern1, replacement1, text)
        logger.debug(f"パターン1適用後: {fixed_text[:300]!r}...")

        # 2. エラー行の列116付近の問題を修正するための特別なパターン
        # 例: {"jsonrpc":"2.0","error...4dfc-825d-4d51afa4da30}
        pattern2 = r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})}"
        replacement2 = r'"\1"}'
        fixed_text = re.sub(pattern2, replacement2, fixed_text)
        logger.debug(f"パターン2適用後: {fixed_text[:300]!r}...")

        # 3. エラーメッセージから特定した列116付近の問題に対する特別な修正
        # 例: "error...42e6-aa5b-b6c9f3f32620}
        pattern3 = r'"error([^"]*?)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})}'
        replacement3 = r'"error\1"\2"}'
        fixed_text = re.sub(pattern3, replacement3, fixed_text)
        logger.debug(f"パターン3適用後: {fixed_text[:300]!r}...")

        # 4. 一般的なUUIDパターンを検出して引用符で囲む
        pattern4 = r'([^":\s,\{\[])([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})([^":\s,\}\]])'
        replacement4 = r'\1"\2"\3'
        fixed_text = re.sub(pattern4, replacement4, fixed_text)
        logger.debug(f"パターン4適用後: {fixed_text[:300]!r}...")

        # 5. 行末のUUIDパターンを検出して引用符で囲む
        pattern5 = r'([^":\s,\{\[])([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$'
        replacement5 = r'\1"\2"'
        fixed_text = re.sub(pattern5, replacement5, fixed_text)
        logger.debug(f"パターン5適用後: {fixed_text[:300]!r}...")

        # 6. 行頭のUUIDパターンを検出して引用符で囲む
        pattern6 = r'^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})([^":\s,\}\]])'
        replacement6 = r'"\1"\2'
        fixed_text = re.sub(pattern6, replacement6, fixed_text)
        logger.debug(f"パターン6適用後: {fixed_text[:300]!r}...")

        # 7. 特定のエラーパターンを修正
        if "error" in fixed_text and "column 116" in text and len(fixed_text) > 120:
            logger.debug(f"列116付近の文字: {fixed_text[110:120]!r}")

            # 特定の位置に引用符を挿入
            try:
                chars = list(fixed_text)
                if len(chars) > 115 and chars[115] not in ['"', "'"]:
                    chars.insert(115, '"')
                    logger.debug("列115に引用符を挿入しました")
                if len(chars) > 117 and chars[117] not in ['"', "'"]:
                    chars.insert(117, '"')
                    logger.debug("列117に引用符を挿入しました")
                fixed_text = "".join(chars)
            except Exception as e:
                logger.error(f"特定位置への引用符挿入中にエラーが発生: {e}")

        if fixed_text != text:
            logger.info("UUID形式を修正しました")
            logger.debug(f"修正前: {text[:200]!r}...")
            logger.debug(f"修正後: {fixed_text[:200]!r}...")

            # JSONとして解析できるか確認
            try:
                json.loads(fixed_text)
                logger.info("修正後のJSONは有効です")
            except json.JSONDecodeError as e:
                logger.warning(f"修正後のJSONは依然として無効です: {e}")

        return fixed_text.encode("utf-8") if isinstance(content, bytes) else fixed_text

    @classmethod
    def _log_json_data(cls, json_data: Any) -> None:
        """JSONデータをログに出力する"""
        if isinstance(json_data, bytes):
            logger.debug(f"JSON (bytes): {json_data[:300]!r}...")
        else:
            logger.debug(f"JSON (str): {json_data[:300]!r}...")

    @classmethod
    def _handle_validation_error(cls, fixed_json: Any, error_msg: str, **kwargs: Any) -> Any:
        """JSONの検証エラーを処理する"""
        if "column" not in error_msg or not isinstance(fixed_json, (str, bytes)):
            return None

        try:
            # エラー位置を特定
            col_match = re.search(r"column (\d+)", error_msg)
            if not col_match:
                return None

            col_pos = int(col_match.group(1))
            logger.debug(f"エラー位置: 列 {col_pos}")

            # エラー周辺の文字を表示
            start_pos = max(0, col_pos - 10)
            end_pos = min(len(fixed_json), col_pos + 10)
            context = fixed_json[start_pos:end_pos]
            if isinstance(context, bytes):
                context = context.decode("utf-8", errors="replace")
            logger.debug(f"エラー周辺の文字: {context!r}")

            # 特定の位置に引用符を挿入する緊急修正
            if isinstance(fixed_json, bytes):
                text = fixed_json.decode("utf-8", errors="replace")
            else:
                text = fixed_json

            # 問題の位置に引用符を挿入
            chars = list(text)
            if col_pos < len(chars):
                if chars[col_pos - 1] not in ['"', "'"]:
                    chars.insert(col_pos - 1, '"')
                    logger.debug(f"列 {col_pos - 1} に引用符を挿入しました")
                if col_pos < len(chars) and chars[col_pos] not in ['"', "'"]:
                    chars.insert(col_pos, '"')
                    logger.debug(f"列 {col_pos} に引用符を挿入しました")

            emergency_fixed = "".join(chars)
            logger.debug(f"緊急修正後: {emergency_fixed[:300]!r}...")

            try:
                # 緊急修正したJSONで再度検証
                result = cls._original_validate_json(json_data=emergency_fixed, **kwargs)
                logger.info("緊急修正後のJSONの検証に成功しました")
                return result
            except Exception as e2:
                logger.error(f"緊急修正後のJSONの検証にも失敗しました: {e2}")
                return None
        except Exception as ex:
            logger.error(f"緊急修正中にエラーが発生しました: {ex}")
            return None

    @staticmethod
    def _patched_json_validate(json_data: Any, **kwargs: Any) -> Any:
        """パッチされたJSON検証メソッド"""
        try:
            # 元のデータをログ出力
            UUIDFixer._log_json_data(json_data)

            # UUIDフォーマットを修正
            fixed_json = UUIDFixer.fix_uuid_format(json_data)

            # 修正後のデータをログ出力
            UUIDFixer._log_json_data(fixed_json)

            try:
                # 修正したJSONで検証を試みる
                result = UUIDFixer._original_validate_json(json_data=fixed_json, **kwargs)
                logger.info("JSONの検証に成功しました")
                return result
            except Exception as e:
                logger.error(f"修正後のJSONの検証に失敗しました: {e}")

                # エラーメッセージから問題の箇所を特定
                error_result = UUIDFixer._handle_validation_error(fixed_json, str(e), **kwargs)
                if error_result is not None:
                    return error_result

                # 元のJSONデータを使用して再試行
                logger.info("元のJSONデータを使用して再試行します")
                return UUIDFixer._original_validate_json(json_data=json_data, **kwargs)
        except Exception as e:
            logger.error(f"モンキーパッチ内でエラーが発生しました: {e}")
            # 元のメソッドを使用
            return UUIDFixer._original_validate_json(json_data=json_data, **kwargs)

    @classmethod
    def apply_patch(cls, json_rpc_message_class) -> None:
        """
        JSONRPCMessageのmodel_validate_jsonメソッドをモンキーパッチ

        Args:
            json_rpc_message_class: JSONRPCMessageクラス
        """
        # 元のメソッドを保存
        if cls._original_validate_json is None:
            cls._original_validate_json = json_rpc_message_class.model_validate_json
            logger.info("強化されたUUIDフィクサーを適用しました")

        # モンキーパッチを適用
        json_rpc_message_class.model_validate_json = cls._patched_json_validate

    @classmethod
    def remove_patch(cls, json_rpc_message_class) -> None:
        """
        モンキーパッチを元に戻す

        Args:
            json_rpc_message_class: JSONRPCMessageクラス
        """
        # 元のメソッドが保存されている場合のみ戻す
        if cls._original_validate_json is not None:
            json_rpc_message_class.model_validate_json = cls._original_validate_json
            cls._original_validate_json = None
            logger.info("UUIDフィクサーを削除しました")
