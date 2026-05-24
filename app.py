import streamlit as st
from collections import deque
import pandas as pd
from datetime import datetime

# ---------------------------- Data Model ----------------------------
class Member:
    def __init__(self, id, name, sponsor_id, parent_id=None, is_active=True):
        self.id = id
        self.name = name
        self.sponsor_id = sponsor_id          # untuk Auto Rich (referral)
        self.parent_id = parent_id            # untuk Auto Cuan (placement)
        self.left_child_id = None
        self.right_child_id = None
        self.is_active = is_active            # status Auto Cuan bulan ini
        self.balance_cuan = 0
        self.balance_rich = 0
        self.total_spent = 0

# ---------------------------- Helper Functions ----------------------------
def init_session():
    if 'members' not in st.session_state:
        root = Member(1, "Perusahaan", sponsor_id=None, parent_id=None, is_active=True)
        st.session_state.members = {1: root}
        st.session_state.next_id = 2
        st.session_state.total_cash_in = 0
        st.session_state.total_bonus_cuan = 0
        st.session_state.total_bonus_rich = 0
        st.session_state.total_sponsor_bonus = 0
        st.session_state.transactions = []
        st.session_state.selected_sponsor_id = 1
        st.session_state.reg_name = ""
        # Default komisi (bisa diubah user)
        st.session_state.komisi_reguler = 4000
        st.session_state.komisi_last_ancestor = 9000
        st.session_state.komisi_sponsor = 1000
        st.session_state.komisi_rich_per_level = 5000
        st.session_state.max_level = 7
        st.session_state.last_ancestor_position = "Level Tertinggi (paling dekat root)"

def find_placement_cuan():
    """Cari posisi kosong di binary tree (root = member 1) dengan BFS prioritas kanan dulu"""
    members = st.session_state.members
    root_id = 1
    if root_id not in members:
        return None, None
    queue = deque([root_id])
    while queue:
        node_id = queue.popleft()
        node = members[node_id]
        # prioritas kanan
        if node.right_child_id is None:
            return node_id, False  # False = kanan
        if node.left_child_id is None:
            return node_id, True   # True = kiri
        # jika kedua anak ada, masukkan ke queue untuk level berikutnya
        queue.append(node.right_child_id)
        queue.append(node.left_child_id)
    return None, None

def register_member(sponsor_id, name):
    members = st.session_state.members
    if sponsor_id not in members:
        return None, f"Sponsor ID {sponsor_id} tidak ditemukan."
    for m in members.values():
        if m.name.lower() == name.lower():
            return None, f"Nama '{name}' sudah terdaftar."
    new_id = st.session_state.next_id
    st.session_state.next_id += 1

    # Placement untuk Auto Cuan (binary tree dari root)
    parent_id, is_left = find_placement_cuan()
    if parent_id is None:
        return None, "Tidak ada slot kosong di binary tree."

    # Member baru langsung aktif
    new_member = Member(new_id, name, sponsor_id, parent_id, is_active=True)
    members[new_id] = new_member
    parent = members[parent_id]
    if not is_left:
        parent.right_child_id = new_id
    else:
        parent.left_child_id = new_id

    posisi = "kanan" if not is_left else "kiri"
    info = (f"✅ Auto Cuan: anak {posisi} dari {parent.name} (ID:{parent.id})\n"
            f"✅ Auto Rich: sponsor langsung = {members[sponsor_id].name} (ID:{sponsor_id})")
    return new_member, info

def get_ancestors_cuan(member_id, members, max_level):
    ancestors = []
    cur = members[member_id].parent_id
    level = 1
    while cur and level <= max_level:
        ancestors.append((cur, level))
        cur = members[cur].parent_id
        level += 1
    return ancestors

def get_ancestors_rich(member_id, members, max_level):
    ancestors = []
    cur = members[member_id].sponsor_id
    level = 1
    while cur and level <= max_level:
        ancestors.append((cur, level))
        cur = members[cur].sponsor_id
        level += 1
    return ancestors

def process_transaction_cuan(member_id, amount, apply_to_balance=False):
    members = st.session_state.members
    member = members[member_id]
    member.is_active = (amount >= 100000)  # update status berdasarkan belanja
    if apply_to_balance:
        member.total_spent += amount
        st.session_state.total_cash_in += amount

    bonus_cuan = 0
    breakdown_cuan = []
    if member.is_active:
        max_level = st.session_state.max_level
        ancestors = get_ancestors_cuan(member_id, members, max_level)
        valid = []
        for anc_id, lvl in ancestors:
            if members[anc_id].is_active:
                valid.append((anc_id, lvl))
            else:
                break
        n = len(valid)
        komisi_reg = st.session_state.komisi_reguler
        komisi_last = st.session_state.komisi_last_ancestor
        if st.session_state.last_ancestor_position == "Level Tertinggi (paling dekat root)":
            last_index = n - 1
        else:
            last_index = 0
        for i, (anc_id, lvl) in enumerate(valid):
            komisi = komisi_last if i == last_index else komisi_reg
            if apply_to_balance:
                members[anc_id].balance_cuan += komisi
                st.session_state.total_bonus_cuan += komisi
            bonus_cuan += komisi
            nama = members[anc_id].name
            posisi = "Last Ancestor" if i == last_index else "Reguler"
            deskripsi = f"Matrix Level {lvl} ({posisi}) Rp{komisi:,}"
            breakdown_cuan.append((anc_id, nama, deskripsi, komisi))
    sponsor_id = member.sponsor_id
    if sponsor_id and sponsor_id in members:
        komisi_sp = st.session_state.komisi_sponsor
        if apply_to_balance:
            members[sponsor_id].balance_cuan += komisi_sp
            st.session_state.total_bonus_cuan += komisi_sp
        bonus_cuan += komisi_sp
        nama_sp = members[sponsor_id].name
        breakdown_cuan.append((sponsor_id, nama_sp, f"Bonus Sponsor Rp{komisi_sp:,}", komisi_sp))

    return {
        'buyer_name': member.name,
        'buyer_id': member_id,
        'amount': amount,
        'member_active': member.is_active,
        'ancestors_cuan': [(aid, lvl) for aid, lvl in ancestors],
        'bonus_cuan': bonus_cuan,
        'bonus_rich': 0,
        'total_bonus': bonus_cuan,
        'breakdown_cuan': breakdown_cuan,
        'breakdown_rich': []
    }

def process_transaction_rich(member_id, amount, apply_to_balance=False):
    members = st.session_state.members
    member = members[member_id]
    if apply_to_balance:
        member.total_spent += amount
        st.session_state.total_cash_in += amount

    bonus_rich = 0
    breakdown_rich = []
    max_level = st.session_state.max_level
    komisi_per_level = st.session_state.komisi_rich_per_level
    ancestors_rich = get_ancestors_rich(member_id, members, max_level)
    for anc_id, lvl in ancestors_rich:
        komisi = komisi_per_level
        if apply_to_balance:
            members[anc_id].balance_rich += komisi
            st.session_state.total_bonus_rich += komisi
        bonus_rich += komisi
        nama = members[anc_id].name
        breakdown_rich.append((anc_id, nama, f"Level {lvl} Rp{komisi:,}", komisi))
    return {
        'buyer_name': member.name,
        'buyer_id': member_id,
        'amount': amount,
        'member_active': member.is_active,
        'bonus_cuan': 0,
        'bonus_rich': bonus_rich,
        'total_bonus': bonus_rich,
        'breakdown_cuan': [],
        'breakdown_rich': breakdown_rich
    }

def get_descendants_rich(root_id, members):
    result = []
    stack = [root_id]
    while stack:
        nid = stack.pop()
        if nid not in result:
            result.append(nid)
        for mid, m in members.items():
            if m.sponsor_id == nid:
                stack.append(mid)
    return result

def get_member_tree_cuan(root_id, members, search_id=None):
    if root_id not in members:
        return ""
    lines = ['digraph G {', 
             '    rankdir=LR;',   # Left to Right agar lebih lebar
             '    node [shape=box, style=filled, fillcolor=lightblue, fontname="Arial", fontsize=14, width=1.8, height=0.8];',
             '    splines=polyline;',
             '    nodesep=0.8;',
             '    ranksep=0.8;',
             '    margin=0.2;']
    queue = deque([root_id])
    while queue:
        nid = queue.popleft()
        node = members[nid]
        if search_id == nid:
            fillcolor = "yellow"
            fontcolor = "black"
        else:
            if node.is_active:
                fillcolor = "lightgreen"
            else:
                fillcolor = "lightgray"
            fontcolor = "black"
        label = f"{node.name}\\n(ID:{nid})\\n{'Aktif' if node.is_active else 'Tdk Aktif'}"
        lines.append(f'    "{nid}" [label="{label}", fillcolor="{fillcolor}", fontcolor="{fontcolor}"];')
        if node.left_child_id:
            lines.append(f'    "{nid}" -> "{node.left_child_id}" [arrowsize=0.7];')
            queue.append(node.left_child_id)
        if node.right_child_id:
            lines.append(f'    "{nid}" -> "{node.right_child_id}" [arrowsize=0.7];')
            queue.append(node.right_child_id)
    lines.append('}')
    return "\n".join(lines)

def get_member_tree_rich(root_id, members, search_id=None):
    descendants = get_descendants_rich(root_id, members)
    if not descendants:
        return ""
    lines = ['digraph G {', 
             '    rankdir=TB;',   # Top to Bottom untuk sponsor tree
             '    node [shape=box, style=filled, fillcolor=lightblue, fontname="Arial", fontsize=14, width=1.8, height=0.8];',
             '    splines=polyline;',
             '    nodesep=0.8;',
             '    ranksep=0.8;',
             '    margin=0.2;']
    for nid in descendants:
        node = members[nid]
        if search_id == nid:
            fillcolor = "yellow"
            fontcolor = "black"
        else:
            fillcolor = "lightgreen"
            fontcolor = "black"
        label = f"{node.name}\\n(ID:{nid})\\nSaldo R: {node.balance_rich:,}"
        lines.append(f'    "{nid}" [label="{label}", fillcolor="{fillcolor}", fontcolor="{fontcolor}"];')
    for nid in descendants:
        node = members[nid]
        if node.sponsor_id and node.sponsor_id in descendants:
            lines.append(f'    "{node.sponsor_id}" -> "{nid}" [arrowsize=0.7];')
    lines.append('}')
    return "\n".join(lines)

def create_sample_network():
    members = st.session_state.members
    if len(members) > 1:
        st.warning("Jaringan sudah memiliki member. Reset terlebih dahulu.")
        return
    regs = [
        (1, "Member 1"), (1, "Member 2"),
        (2, "Member 3"), (2, "Member 4"),
        (3, "Member 5"), (3, "Member 6"),
        (4, "Member 7"), (4, "Member 8"),
        (5, "Member 9"), (5, "Member 10"),
    ]
    for sponsor_id, name in regs:
        new, info = register_member(sponsor_id, name)
        if new:
            st.success(f"{name} (ID:{new.id}) berhasil.")
        else:
            st.error(f"Gagal: {info}")
    st.info("Sample jaringan 10 member selesai. Semua member aktif secara default.")

def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.clear()
    init_session()
    st.rerun()

def product_card(product, member_id):
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        st.image("https://placehold.co/80x80?text=Produk", width=80)
    with col2:
        st.markdown(f"**{product['name']}**  \n{product['desc']}  \n💎 Harga: Rp{product['price']:,.0f}")
    with col3:
        if st.button(f"Beli", key=f"buy_{product['id']}_{member_id}"):
            if product['type'] == 'cuan':
                res = process_transaction_cuan(member_id, product['price'], apply_to_balance=True)
            else:
                res = process_transaction_rich(member_id, product['price'], apply_to_balance=True)
            if res:
                tx_detail = []
                if product['type'] == 'cuan':
                    for (mid, nama, desc, nominal) in res['breakdown_cuan']:
                        tx_detail.append({
                            "Member ID": mid,
                            "Nama Member": nama,
                            "Keterangan": desc,
                            "Nominal (Rp)": nominal
                        })
                else:
                    for (mid, nama, desc, nominal) in res['breakdown_rich']:
                        tx_detail.append({
                            "Member ID": mid,
                            "Nama Member": nama,
                            "Keterangan": desc,
                            "Nominal (Rp)": nominal
                        })
                tx = {
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'pembeli': res['buyer_name'],
                    'pembeli_id': res['buyer_id'],
                    'nominal': res['amount'],
                    'jenis': 'Auto Cuan' if product['type'] == 'cuan' else 'Auto Rich',
                    'total_komisi': res['total_bonus'],
                    'detail_komisi': tx_detail
                }
                st.session_state.transactions.append(tx)
                st.success(f"✅ Berhasil membeli {product['name']}!")
                st.info(f"Total Komisi: Rp{res['total_bonus']:,.0f}")
                if product['type'] == 'cuan':
                    st.write("**Jalur ancestor (dari bawah ke atas):**")
                    if 'ancestors_cuan' in res:
                        for aid, lvl in res['ancestors_cuan']:
                            st.write(f"Level {lvl}: {st.session_state.members[aid].name} (ID:{aid})")
                df = pd.DataFrame(tx_detail)
                st.dataframe(df, use_container_width=True)
                st.balloons()
            else:
                st.error("Gagal transaksi")

def main():
    st.set_page_config(page_title="K-BBPT Simulator", layout="wide")
    st.title("🛍️ K-BBPT Simulator - Belanja & Komisi")
    st.markdown("**Auto Cuan** (belanja ≥ Rp100.000) | **Auto Rich** (belanja bebas)")

    init_session()

    with st.sidebar:
        st.header("🛠️ Manajemen")
        if st.button("🌳 Sample Jaringan 10 Member", use_container_width=True):
            create_sample_network()
        if st.button("🗑️ Reset Aplikasi", use_container_width=True):
            reset_app()
        st.markdown("---")
        st.header("⚙️ Pengaturan Komisi")
        st.session_state.komisi_reguler = st.number_input("Komisi Matrix Reguler (per level)", min_value=0, value=4000, step=500, key="reg")
        st.session_state.komisi_last_ancestor = st.number_input("Komisi Last Ancestor Bonus", min_value=0, value=9000, step=500, key="last")
        st.session_state.komisi_sponsor = st.number_input("Bonus Sponsor Langsung", min_value=0, value=1000, step=500, key="spons")
        st.session_state.komisi_rich_per_level = st.number_input("Komisi Auto Rich per Level", min_value=0, value=5000, step=500, key="rich")
        st.session_state.max_level = st.number_input("Maksimal Level Komisi (1-7)", min_value=1, max_value=7, value=7, step=1, key="maxlvl")
        st.session_state.last_ancestor_position = st.selectbox(
            "Posisi Last Ancestor Bonus",
            options=["Level Tertinggi (paling dekat root)", "Level Terendah (parent langsung pembayar)"],
            index=0
        )
        st.markdown("---")
        st.header("📊 Ringkasan Cepat")
        total_member = len(st.session_state.members)
        total_cash_in = st.session_state.total_cash_in
        total_bonus = st.session_state.total_bonus_cuan + st.session_state.total_bonus_rich
        nett = total_cash_in - total_bonus
        st.metric("Total Member", total_member)
        st.metric("Cash In", f"Rp{total_cash_in:,.0f}")
        st.metric("Total Bonus", f"Rp{total_bonus:,.0f}")
        st.metric("Nett Perusahaan", f"Rp{nett:,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs(["🏪 Belanja Produk", "📊 Dashboard", "📝 Registrasi", "🌳 Visualisasi"])

    with tab1:
        st.header("🛒 Toko Produk K-BBPT")
        member_options = {m.id: f"{m.name} (ID:{m.id})" for m in st.session_state.members.values()}
        if not member_options:
            st.warning("Belum ada member. Silakan registrasi.")
            buyer_id = None
        else:
            buyer_id = st.selectbox("👤 Member yang berbelanja", options=list(member_options.keys()), format_func=lambda x: member_options[x])
        filter_type = st.radio("Tampilkan produk:", ["Semua", "Auto Cuan (wajib)", "Auto Rich (bebas)"], horizontal=True)
        products = [
            {"id": 1, "name": "Paket Keanggotaan Bulanan", "desc": "Wajib Auto Cuan - Minimal Rp100.000", "price": 100000, "type": "cuan"},
            {"id": 2, "name": "Paket Keanggotaan Bulanan+", "desc": "Auto Cuan - Stok produk", "price": 200000, "type": "cuan"},
            {"id": 3, "name": "Suplemen Kesehatan", "desc": "Auto Rich - Harga reseller", "price": 50000, "type": "rich"},
            {"id": 4, "name": "Vitamin C 1000mg", "desc": "Auto Rich - Bisa dijual", "price": 25000, "type": "rich"},
            {"id": 5, "name": "Paket Herbal (3 botol)", "desc": "Auto Rich - Diskon", "price": 120000, "type": "rich"},
            {"id": 6, "name": "Alat Kesehatan Digital", "desc": "Auto Rich - Grosir", "price": 350000, "type": "rich"},
        ]
        filtered = [p for p in products if filter_type == "Semua" or (filter_type == "Auto Cuan (wajib)" and p['type']=='cuan') or (filter_type == "Auto Rich (bebas)" and p['type']=='rich')]
        if buyer_id:
            cols = st.columns(2)
            for i, prod in enumerate(filtered):
                with cols[i % 2]:
                    product_card(prod, buyer_id)
        else:
            st.info("Silakan registrasi member dulu.")

    with tab2:
        st.header("📊 Dashboard Lengkap")
        col1, col2, col3 = st.columns(3)
        total_member = len(st.session_state.members)
        active_member = sum(1 for m in st.session_state.members.values() if m.is_active)
        col1.metric("Total Member", total_member)
        col2.metric("Member Aktif (Auto Cuan)", active_member)
        col3.metric("Total Cash In", f"Rp{st.session_state.total_cash_in:,.0f}")
        col4, col5, col6 = st.columns(3)
        col4.metric("Total Bonus Auto Cuan", f"Rp{st.session_state.total_bonus_cuan:,.0f}")
        col5.metric("Total Bonus Auto Rich", f"Rp{st.session_state.total_bonus_rich:,.0f}")
        nett = st.session_state.total_cash_in - (st.session_state.total_bonus_cuan + st.session_state.total_bonus_rich)
        col6.metric("Nett Perusahaan", f"Rp{nett:,.0f}")

        st.subheader("📜 Riwayat Transaksi & Komisi")
        if st.session_state.transactions:
            for tx in reversed(st.session_state.transactions[-20:]):
                with st.expander(f"{tx['timestamp']} - {tx['pembeli']} belanja Rp{tx['nominal']:,} ({tx['jenis']}) - Total Komisi: Rp{tx['total_komisi']:,}"):
                    df_tx = pd.DataFrame(tx['detail_komisi'])
                    st.dataframe(df_tx, use_container_width=True)
        else:
            st.info("Belum ada transaksi.")

        st.subheader("📋 Daftar Member")
        df_data = []
        for m in st.session_state.members.values():
            df_data.append({
                "ID": m.id, "Nama": m.name, "Sponsor (Auto Rich)": m.sponsor_id,
                "Parent Cuan": m.parent_id, "Status": "✅" if m.is_active else "❌",
                "Balance Cuan": m.balance_cuan, "Balance Rich": m.balance_rich,
                "Total Belanja": m.total_spent
            })
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)

    with tab3:
        st.header("📝 Registrasi Member Baru")
        new_name = st.text_input("Nama Lengkap", value=st.session_state.reg_name)
        st.session_state.reg_name = new_name
        sponsor_list = [(m.id, f"{m.name} (ID:{m.id})") for m in st.session_state.members.values()]
        # default selected sponsor = 1 (Perusahaan)
        current_index = 0
        for i, (sid, _) in enumerate(sponsor_list):
            if sid == st.session_state.selected_sponsor_id:
                current_index = i
                break
        selected_sponsor = st.selectbox("Pilih Sponsor", options=sponsor_list, format_func=lambda x: x[1], index=current_index)
        st.session_state.selected_sponsor_id = selected_sponsor[0]
        if st.button("Daftarkan"):
            if not new_name.strip():
                st.error("Nama tidak boleh kosong")
            else:
                new_member, info = register_member(st.session_state.selected_sponsor_id, new_name.strip())
                if new_member:
                    st.success(f"🎉 Member {new_member.name} (ID:{new_member.id}) berhasil!")
                    st.info(info)
                    st.session_state.reg_name = ""
                    # Reset sponsor ke Perusahaan (ID 1) setelah daftar
                    st.session_state.selected_sponsor_id = 1
                    st.rerun()
                else:
                    st.error(info)

    with tab4:
        st.header("🌳 Visualisasi Jaringan")
        net_type = st.radio("Pilih jenis jaringan", ["Auto Cuan (Binary / Placement)", "Auto Rich (Sponsor Tree)"])
        root_options = {m.id: f"{m.name} (ID:{m.id})" for m in st.session_state.members.values()}
        root_id = st.selectbox("Root / Member awal", options=list(root_options.keys()), format_func=lambda x: root_options[x])
        search_term = st.text_input("🔍 Cari member (nama atau ID)", placeholder="Contoh: Member 1 atau ID 5")
        search_id = None
        if search_term:
            search_term_lower = search_term.lower()
            for m in st.session_state.members.values():
                if search_term_lower == m.name.lower() or search_term == str(m.id):
                    search_id = m.id
                    break
            if search_id is None:
                st.warning("Member tidak ditemukan.")
        if net_type == "Auto Cuan (Binary / Placement)":
            dot = get_member_tree_cuan(root_id, st.session_state.members, search_id)
        else:
            dot = get_member_tree_rich(root_id, st.session_state.members, search_id)
        if dot:
            st.graphviz_chart(dot, use_container_width=True)
            st.caption("💡 Tips: Gunakan Ctrl + Scroll untuk zoom. Klik kanan pada gambar untuk menyimpan.")
        else:
            st.warning("Pohon kosong atau root tidak ditemukan.")

if __name__ == "__main__":
    main()
