import streamlit as st
import requests
import json
from datetime import datetime, timedelta
import time
import os

# ページ設定
st.set_page_config(
    page_title="ARK Server Manager",
    page_icon="🦖",
    layout="wide"
)

# セッション状態の初期化
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'token' not in st.session_state:
    st.session_state.token = None
if 'token_expires' not in st.session_state:
    st.session_state.token_expires = None
if 'vps_start_time' not in st.session_state:
    st.session_state.vps_start_time = None

# ConoHa API クラス
class ConoHaAPI:
    def __init__(self, username, password, tenant_id):
        self.username = username
        self.password = password
        self.tenant_id = tenant_id
        self.endpoints = {}
        
    def authenticate(self):
        """ConoHa API認証"""
        auth_url = "https://identity.tyo1.conoha.io/v2.0/tokens"
        auth_data = {
            "auth": {
                "passwordCredentials": {
                    "username": self.username,
                    "password": self.password
                },
                "tenantId": self.tenant_id
            }
        }
        
        try:
            response = requests.post(auth_url, json=auth_data)
            if response.status_code == 200:
                data = response.json()
                st.session_state.token = data['access']['token']['id']
                st.session_state.token_expires = datetime.fromisoformat(
                    data['access']['token']['expires'].replace('Z', '+00:00')
                )
                
                # エンドポイント保存
                for service in data['access']['serviceCatalog']:
                    if service['type'] == 'compute':
                        self.endpoints['compute'] = service['endpoints'][0]['publicURL']
                
                st.session_state.authenticated = True
                return True
        except Exception as e:
            st.error(f"認証エラー: {e}")
            return False
    
    def get_server_list(self):
        """VPS一覧取得"""
        if not st.session_state.token:
            return []
        
        headers = {"X-Auth-Token": st.session_state.token}
        try:
            response = requests.get(
                f"{self.endpoints['compute']}/servers/detail",
                headers=headers
            )
            if response.status_code == 200:
                return response.json()['servers']
        except:
            pass
        return []
    
    def get_server_status(self, server_id):
        """VPS状態取得"""
        headers = {"X-Auth-Token": st.session_state.token}
        try:
            response = requests.get(
                f"{self.endpoints['compute']}/servers/{server_id}",
                headers=headers
            )
            if response.status_code == 200:
                return response.json()['server']
        except:
            pass
        return None
    
    def start_server(self, server_id):
        """VPS起動"""
        headers = {"X-Auth-Token": st.session_state.token}
        try:
            response = requests.post(
                f"{self.endpoints['compute']}/servers/{server_id}/action",
                headers=headers,
                json={"os-start": None}
            )
            return response.status_code == 202
        except:
            return False
    
    def stop_server(self, server_id):
        """VPS停止"""
        headers = {"X-Auth-Token": st.session_state.token}
        try:
            response = requests.post(
                f"{self.endpoints['compute']}/servers/{server_id}/action",
                headers=headers,
                json={"os-stop": None}
            )
            return response.status_code == 202
        except:
            return False
    
    def reboot_server(self, server_id):
        """VPS再起動"""
        headers = {"X-Auth-Token": st.session_state.token}
        try:
            response = requests.post(
                f"{self.endpoints['compute']}/servers/{server_id}/action",
                headers=headers,
                json={"reboot": {"type": "SOFT"}}
            )
            return response.status_code == 202
        except:
            return False

# Discord Webhook通知
def send_discord_notification(message, webhook_url=None):
    """Discord通知送信"""
    if not webhook_url:
        return
    
    try:
        data = {
            "content": message,
            "username": "ARK Server Manager",
            "avatar_url": "https://img.icons8.com/color/96/000000/ark-survival-evolved.png"
        }
        requests.post(webhook_url, json=data)
    except:
        pass

# メイン画面
def main():
    st.title("🦖 ARK Server Manager")
    st.markdown("ConoHa VPS ARKサーバー管理システム")
    
    # サイドバー - 認証
    with st.sidebar:
        st.header("⚙️ 設定")
        
        # API認証情報
        with st.expander("API設定", expanded=not st.session_state.authenticated):
            username = st.text_input("ConoHa APIユーザー名", value=st.secrets.get("CONOHA_USERNAME", ""))
            password = st.text_input("ConoHa APIパスワード", type="password", value=st.secrets.get("CONOHA_PASSWORD", ""))
            tenant_id = st.text_input("テナントID", value=st.secrets.get("CONOHA_TENANT_ID", ""))
            server_id = st.text_input("サーバーID", value=st.secrets.get("VPS_SERVER_ID", ""))
            
            if st.button("接続", type="primary"):
                api = ConoHaAPI(username, password, tenant_id)
                if api.authenticate():
                    st.success("✅ 接続成功！")
                    st.rerun()
                else:
                    st.error("❌ 接続失敗")
        
        # Discord Webhook
        with st.expander("Discord通知"):
            webhook_url = st.text_input(
                "Webhook URL",
                value=st.secrets.get("DISCORD_WEBHOOK", ""),
                type="password"
            )
        
        # 料金計算
        st.divider()
        st.subheader("💰 料金計算")
        hourly_rate = 6.6
        
        hours = st.slider("使用時間（時間）", 0, 24, 4)
        daily_cost = hourly_rate * hours
        monthly_cost = daily_cost * 30
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("日額", f"{daily_cost:.0f}円")
        with col2:
            st.metric("月額予想", f"{monthly_cost:.0f}円")
        
        st.info("月額上限: 3,608円")
    
    # メインコンテンツ
    if not st.session_state.authenticated:
        st.warning("⚠️ 左のサイドバーでAPI設定を行ってください")
        
        # 使い方
        with st.expander("📖 使い方"):
            st.markdown("""
            ### 初期設定
            1. ConoHaコントロールパネルでAPI情報を取得
            2. 左のAPI設定に入力
            3. 「接続」ボタンをクリック
            
            ### VPS管理
            - 🟢 **起動**: VPSを起動（ARKも自動起動）
            - 🔴 **停止**: VPSを完全停止（料金停止）
            - 🔄 **再起動**: VPSを再起動
            
            ### 料金について
            - 起動時のみ課金（6.6円/時間）
            - 停止中は0円
            - 月額上限3,608円
            """)
    else:
        # API接続済み
        api = ConoHaAPI(
            st.secrets.get("CONOHA_USERNAME", username),
            st.secrets.get("CONOHA_PASSWORD", password),
            st.secrets.get("CONOHA_TENANT_ID", tenant_id)
        )
        api.endpoints['compute'] = st.session_state.token and f"https://compute.tyo1.conoha.io/v2/{tenant_id}" or ""
        
        # サーバー情報取得
        server = api.get_server_status(server_id) if 'server_id' in locals() else None
        
        if server:
            # ステータス表示
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                status = server['status']
                if status == 'ACTIVE':
                    st.success(f"🟢 稼働中")
                elif status == 'SHUTOFF':
                    st.error(f"🔴 停止中")
                else:
                    st.warning(f"⏳ {status}")
            
            with col2:
                # IPアドレス取得
                ip = None
                for net in server.get('addresses', {}).values():
                    for addr in net:
                        if addr['version'] == 4:
                            ip = addr['addr']
                            break
                if ip:
                    st.info(f"📍 IP: {ip}")
            
            with col3:
                # 作成日時
                created = datetime.fromisoformat(server['created'].replace('Z', '+00:00'))
                if status == 'ACTIVE' and st.session_state.vps_start_time:
                    uptime = datetime.now() - st.session_state.vps_start_time
                    hours = uptime.seconds / 3600
                    st.metric("稼働時間", f"{hours:.1f}時間")
            
            with col4:
                # 料金
                if status == 'ACTIVE' and st.session_state.vps_start_time:
                    hours = (datetime.now() - st.session_state.vps_start_time).seconds / 3600
                    cost = hours * 6.6
                    st.metric("現在の料金", f"{cost:.0f}円")
            
            st.divider()
            
            # 操作ボタン
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("🟢 起動", disabled=(status == 'ACTIVE'), use_container_width=True):
                    with st.spinner("起動中..."):
                        if api.start_server(server_id):
                            st.success("✅ 起動コマンド送信成功！")
                            st.session_state.vps_start_time = datetime.now()
                            send_discord_notification(
                                f"🚀 VPSを起動しました！\n約3-5分後にARKサーバーに接続可能です。\nIP: `{ip}:7777`",
                                webhook_url
                            )
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ 起動失敗")
            
            with col2:
                if st.button("🔴 停止", disabled=(status == 'SHUTOFF'), use_container_width=True):
                    with st.spinner("停止中..."):
                        if api.stop_server(server_id):
                            # 料金計算
                            if st.session_state.vps_start_time:
                                hours = (datetime.now() - st.session_state.vps_start_time).seconds / 3600
                                cost = hours * 6.6
                                message = f"⏸️ VPSを停止しました\n💰 料金: {cost:.0f}円（{hours:.1f}時間）"
                            else:
                                message = "⏸️ VPSを停止しました"
                            
                            st.success("✅ 停止コマンド送信成功！")
                            send_discord_notification(message, webhook_url)
                            st.session_state.vps_start_time = None
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ 停止失敗")
            
            with col3:
                if st.button("🔄 再起動", disabled=(status != 'ACTIVE'), use_container_width=True):
                    with st.spinner("再起動中..."):
                        if api.reboot_server(server_id):
                            st.success("✅ 再起動コマンド送信成功！")
                            send_discord_notification("🔄 VPSを再起動しました", webhook_url)
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ 再起動失敗")
            
            with col4:
                if st.button("🔄 更新", use_container_width=True):
                    st.rerun()
            
            # 詳細情報
            with st.expander("📊 詳細情報"):
                tab1, tab2, tab3 = st.tabs(["サーバー情報", "接続方法", "料金"])
                
                with tab1:
                    st.json({
                        "名前": server['name'],
                        "ID": server['id'],
                        "状態": server['status'],
                        "作成日": server['created'],
                        "フレーバー": server['flavor']['id']
                    })
                
                with tab2:
                    st.markdown(f"""
                    ### Steam での接続方法
                    1. VPSが**稼働中**であることを確認
                    2. Steamを開く
                    3. 表示 → サーバー → お気に入り
                    4. サーバーを追加
                    5. `{ip}:7777` を入力
                    6. 接続
                    
                    ### 注意事項
                    - VPS起動から約3-5分待つ
                    - ARKは自動起動します
                    - Discord Botも自動起動します
                    """)
                
                with tab3:
                    st.markdown("""
                    ### 料金体系
                    - **起動中**: 6.6円/時間
                    - **停止中**: 0円
                    - **月額上限**: 3,608円
                    
                    ### 節約のコツ
                    - 使わない時は必ず停止
                    - 30分無人で自動停止（Discord Bot）
                    - 週末だけなら月500円程度
                    """)
        else:
            st.error("サーバー情報を取得できません")
            if st.button("再認証"):
                st.session_state.authenticated = False
                st.rerun()
    
    # フッター
    st.divider()
    st.caption("🦖 ARK Server Manager - Powered by Streamlit Cloud")

if __name__ == "__main__":
    main()