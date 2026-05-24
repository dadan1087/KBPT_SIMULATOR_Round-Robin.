import streamlit as st
from collections import deque
import pandas as pd
from datetime import datetime

# ---------------------------- Data Model ----------------------------
class Member:
    def __init__(self, id, name, sponsor_id, parent_id=None, is_active=False):
        self.id = id
        self.name = name
        self.sponsor_id = sponsor_id
        self.parent_id = parent_id
        self.left_child_id = None
        self.right_child_id = None
        self.is_active = is_active
        self.balance_cuan = 0
        self.balance_rich = 0
        self.total_spent = 0

# ---------------------------- Algoritma Spillover Round-Robin ----------------------------
# Global placement queue: berisi node yang MASIH PUNYA SLOT KOSONG (kiri atau kanan)
# Diinisialisasi dengan root (1)
# Setiap penempatan: ambil node dari depan, isi slot kanan jika kosong, jika tidak slot kiri.
# Jika setelah diisi node masih punya slot (hanya satu slot yang terisi), kembalikan ke antrian.
# Node baru selalu ditambahkan ke antrian karena punya 2 slot kosong.

def get_placement_parent():
    members = st.session_state.members
    queue = st.session_state.placement_queue

    # Jika antrian kosong (seharusnya tidak terjadi), isi ulang dengan semua node yang punya slot
    if not queue:
        for node in members.values():
            if node.right_child_id is None or node.left_child_id is None:
                queue.append(node.id)

    node_id = queue.popleft()
    node = members[node_id]

    # Prioritas kanan
    if node.right_child_id is None:
        # tempatkan di kanan
        # setelah ini, jika kiri masih kosong, node masih punya slot -> masukkan lagi ke antrian
        if node.left_child_id is None:
            queue.append(node_id)
        return node_id, "kanan"
    elif node.left_child_id is None:
        # tempatkan di kiri
        # node menjadi penuh (karena kanan sudah terisi) -> tidak dikembalikan
        return node_id, "kiri"
    else:
        # Seharusnya tidak pernah sampai ke sini karena node penuh tidak ada di antrian
        return get_placement_parent()  # rekursi aman karena pasti ada node lain

def register_member(sponsor_id, name):
    members = st.session_state.members
    if sponsor_id not in members:
        return None, f"Sponsor ID {sponsor_id} tidak ditemukan."
    if any(m.name.lower() == name.lower() for m in members.values()):
        return None, f"Nama '{name}' sudah terdaftar."

    new_id = st.session_state.next_id
    st.session_state.next_id += 1

    parent_id, side = get_placement_parent()
    if parent_id is None:
        return None, "Tidak ada slot kosong."

    # Member baru aktif
    new_member = Member(new_id, name, sponsor_id, parent_id, is_active=True)
    members[new_id] = new_member
    parent = members[parent_id]

    if side == "kanan":
        parent.right_child_id = new_id
    else:
        parent.left_child_id = new_id

    # Node baru punya 2 slot kosong, masukkan ke antrian
    st.session_state.placement_queue.append(new_id)

    info = f"✅ Auto Cuan: anak {side} dari {parent.name} (ID:{parent.id}) | Auto Rich: sponsor {members[sponsor_id].name}"
    return new_member, info

# ---------------------------- Fungsi komisi (tidak diubah) ----------------------------
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

def calculate_sponsor_bonus_chain(member_id, amount, members, percent):
    total_bonus = 0
    current = member_id
    while current:
        sponsor_id = members[current].sponsor_id
        if sponsor_id is None:
            break
        bonus = int(amount * percent)
        total_bonus += bonus
        members[sponsor_id].balance_cuan += bonus
        st.session_state.total_sponsor_bonus += bonus
        current = sponsor_id
        amount = bonus
    return total_bonus

def process_transaction_cuan(member_id, amount, apply_to_balance=False):
    members = st.session_state.members
    member = members[member_id]
    if amount >= st.session_state.min_spend_active:
        member.is_active = True
    if apply_to_balance:
        member.total_spent += amount
        st.session_state.total_cash_in += amount

    bonus_cuan = 0
    breakdown_cuan = []
    max_level = st.session_state.cuan_max_level
    ancestors = get_ancestors_cuan(member_id, members, max_level)
    for anc_id, lvl in ancestors:
        anc = members[anc_id]
        if anc.is_active:
            percent = st.session_state.cuan_percent[lvl] if lvl < len(st.session_state.cuan_percent) else 0
            komisi = int(amount * percent)
            if komisi > 0:
                if apply_to_balance:
                    anc.balance_cuan += komisi
                    st.session_state.total_bonus_cuan += komisi
                bonus_cuan += komisi
                breakdown_cuan.append((anc_id, anc.name, f"Level {lvl} ({percent*100:.0f}%)", komisi))

    sponsor_bonus_total = 0
    for anc_id, _, _, komisi in breakdown_cuan:
        if komisi > 0:
            sponsor_bonus_total += calculate_sponsor_bonus_chain(anc_id, komisi, members, st.session_state.sponsor_bonus_percent)

    return {
        'buyer_name': member.name, 'buyer_id': member_id, 'amount': amount,
        'member_active': member.is_active, 'ancestors_cuan': ancestors,
        'bonus_cuan': bonus_cuan, 'bonus_rich': 0,
        'total_bonus': bonus_cuan + sponsor_bonus_total,
        'breakdown_cuan': breakdown_cuan, 'breakdown_rich': []
    }

def process_transaction_rich(member_id, amount, apply_to_balance=False):
    members = st.session_state.members
    member = members[member_id]
    if apply_to_balance:
        member.total_spent += amount
        st.session_state.total_cash_in += amount

    bonus_rich = 0
    breakdown_rich = []
    max_level = st.session_state.rich_max_level
    ancestors_rich = get_ancestors_rich(member_id, members, max_level)
    for anc_id, lvl in ancestors_rich:
        percent = st.session_state.rich_percent[lvl] if lvl < len(st.session_state.rich_percent) else 0
        komisi = int(amount * percent)
        if komisi > 0:
            if apply_to_balance:
                members[anc_id].balance_rich += komisi
                st.session_state.total_bonus_rich += komisi
            bonus_rich += komisi
            breakdown_rich.append((anc_id, members[anc_id].name, f"Level {lvl} ({percent*100:.0f}%)", komisi))
    return {
        'buyer_name': member.name, 'buyer_id': member_id, 'amount': amount,
        'member_active': member.is_active, 'bonus_cuan': 0, 'bonus_rich': bonus_rich,
        'total_bonus': bonus_rich, 'breakdown_cuan': [], 'breakdown_rich': breakdown_rich
    }

# ---------------------------- Visualisasi ----------------------------
def get_tree_text(root_id, members, level=0, prefix=""):
    """Menghasilkan representasi teks tree untuk debugging"""
    if root_id not in members:
        return ""
    node = members[root_id]
    lines = []
    indent = "    " * level
    lines.append(f"{indent}├─ {node.name} (ID:{node.id}) {'[AKTIF]' if node.is_active else '[INACTIVE]'}")
    if node.left_child_id:
        lines.extend(get_tree_text(node.left_child_id, members, level+1, "L"))
    if node.right_child_id:
        lines.extend(get_tree_text(node.right_child_id, members, level+1, "R"))
    return lines

def get_member_tree_cuan(root_id, members, search_id=None):
    if root_id not in members:
        return ""
    lines = ['digraph G {', '    rankdir=TB;', '    node [shape=box, style=filled, fillcolor=lightblue, fontname="Arial"];']
    lines.append('    margin=0;')
    queue = deque([root_id])
    while queue:
        nid = queue.popleft()
        node = members[nid]
        if search_id == nid:
            fillcolor = "yellow"
        else:
            fillcolor = "lightgreen" if node.is_active else "lightgray"
        label = f"{node.name}\\n(ID:{nid})\\n{'Aktif' if node.is_active else 'Tdk Aktif'}"
        lines.append(f'    "{nid}" [label="{label}", fillcolor="{fillcolor}"];')
        if node.left_child_id:
            lines.append(f'    "{nid}" -> "{node.left_child_id}";')
            queue.append(node.left_child_id)
        if node.right_child_id:
            lines.append(f'    "{nid}" -> "{node.right_child_id}";')
            queue.append(node.right_child_id)
    lines.append('}')
    return "\n".join(lines)

def get_member_tree_rich(root_id, members, search_id=None):
    # Mencari semua keturunan di sponsor tree
    descendants = set()
    stack = [root_id]
    while stack:
        nid = stack.pop()
        if nid not in descendants:
            descendants.add(nid)
            for mid, m in members.items():
                if m.sponsor_id == nid:
                    stack.append(mid)
    if not descendants:
        return ""
    lines = ['digraph G {', '    rankdir=TB;', '    node [shape=box, style=filled, fillcolor=lightblue, fontname="Arial"];']
    lines.append('    margin=0;')
    for nid in descendants:
        node = members[nid]
        fillcolor = "yellow" if search_id == nid else "lightgreen"
        label = f"{node.name}\\n(ID:{nid})\\nSaldo R: {node.balance_rich:,}"
        lines.append(f'    "{nid}" [label="{label}", fillcolor="{fillcolor}"];')
    for nid in descendants:
        node = members[nid]
        if node.sponsor_id and node.sponsor_id in descendants:
            lines.append(f'    "{node.sponsor_id}" -> "{nid}";')
    lines.append('}')
    return "\n".join(lines)

# ---------------------------- Inisialisasi dan Reset ----------------------------
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
        st.session_state.placement_queue = deque([1])   # antrian round-robin
        st.session_state.selected_sponsor_id = 1
        st.session_state.reg_name = ""
        # Komisi default
        st.session_state.cuan_percent = [0, 0.01, 0.01, 0.05, 0.03, 0.03, 0.02, 0.03, 0.07]
        st.session_state.rich_percent = [0, 0.05, 0.05, 0.04, 0.04, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01]
        st.session_state.cuan_max_level = 8
        st.session_state.rich_max_level = 10
        st.session_state.sponsor_bonus_percent = 0.20
        st.session_state.min_spend_active = 100000

def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session()
    st.rerun()

def create_sample_network():
    if len(st.session_state.members) > 1:
        st.warning("Reset aplikasi terlebih dahulu")
        return
    for sponsor, name in [(1,"Member1"),(1,"Member2"),(2,"Member3"),(2,"Member4"),
                          (3,"Member5"),(3,"Member6"),(4,"Member7"),(4,"Member8")]:
        register_member(sponsor, name)
    st.success("Sample 8 member (binary tree level 3) berhasil dibuat")

# ---------------------------- UI Produk ----------------------------
def product_card(product, member_id):
    col1, col2, col3 = st.columns([1,3,1])
    with col1:
        st.image("https://placehold.co/80x80?text=Produk", width=80)
    with col2:
        st.markdown(f"**{product['name']}**  \n{product['desc']}  \n💎 Harga: Rp{product['price']:,.0f}")
    with col3:
        if st.button("Beli", key=f"buy_{product['id']}_{member_id}"):
            if product['type'] == 'cuan':
                res = process_transaction_cuan(member_id, product['price'], apply_to_balance=True)
            else:
                res = process_transaction_rich(member_id, product['price'], apply_to_balance=True)
            if res:
                tx_detail = []
                for (mid, nama, desc, nominal) in (res['breakdown_cuan'] or res['breakdown_rich']):
                    tx_detail.append({"Member ID": mid, "Nama": nama, "Keterangan": desc, "Rp": nominal})
                st.session_state.transactions.append({
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'pembeli': res['buyer_name'], 'nominal': res['amount'],
                    'jenis': 'Auto Cuan' if product['type']=='cuan' else 'Auto Rich',
                    'total_komisi': res['total_bonus'], 'detail': tx_detail
                })
                st.success(f"✅ Berhasil! Komisi: Rp{res['total_bonus']:,.0f}")
                st.dataframe(pd.DataFrame(tx_detail))
                st.balloons()

# ---------------------------- Main ----------------------------
def main():
    st.set_page_config(page_title="K-BBPT Simulator", layout="wide")
    st.title("🛍️ K-BBPT Simulator - Binary Tree Round-Robin")
    init_session()

    with st.sidebar:
        st.header("Manajemen")
        if st.button("🌳 Sample 8 Member (Binary Tree)"): create_sample_network()
        if st.button("🗑️ Reset Aplikasi"): reset_app()
        st.markdown("---")
        st.header("Pengaturan Komisi")
        st.session_state.min_spend_active = st.number_input("Min belanja aktif", 0, 100000, 100000)
        st.session_state.sponsor_bonus_percent = st.slider("Bonus sponsor (%)", 0, 100, 20)/100.0
        # ... (sederhanakan, biarkan default)

    tab_belanja, tab_dashboard, tab_reg, tab_viz = st.tabs(["🏪 Belanja", "📊 Dashboard", "📝 Registrasi", "🌳 Visualisasi"])

    with tab_belanja:
        buyer = st.selectbox("Member belanja", options=list(st.session_state.members.keys()),
                             format_func=lambda x: f"{st.session_state.members[x].name} (ID:{x})")
        products = [
            {"id":1,"name":"Paket Bulanan","desc":"Auto Cuan","price":100000,"type":"cuan"},
            {"id":3,"name":"Suplemen","desc":"Auto Rich","price":50000,"type":"rich"}
        ]
        for prod in products:
            product_card(prod, buyer)

    with tab_dashboard:
        st.metric("Total Member", len(st.session_state.members))
        st.metric("Cash In", f"Rp{st.session_state.total_cash_in:,.0f}")
        st.dataframe(pd.DataFrame([{
            "ID":m.id, "Nama":m.name, "Parent Cuan":m.parent_id,
            "Kiri":m.left_child_id, "Kanan":m.right_child_id,
            "Aktif":"✅" if m.is_active else "❌"
        } for m in st.session_state.members.values()]))

    with tab_reg:
        name = st.text_input("Nama Member")
        sponsor = st.selectbox("Pilih Sponsor (Auto Rich)", options=list(st.session_state.members.keys()),
                               format_func=lambda x: st.session_state.members[x].name)
        if st.button("Daftar"):
            if name:
                res, msg = register_member(sponsor, name.strip())
                if res:
                    st.success(msg)
                    st.session_state.selected_sponsor_id = 1
                    st.rerun()
                else:
                    st.error(msg)

    with tab_viz:
        st.subheader("Auto Cuan (Binary Placement Tree)")
        dot = get_member_tree_cuan(1, st.session_state.members)
        if dot:
            st.graphviz_chart(dot)
        else:
            st.warning("Tidak bisa render graphviz, silakan install graphviz atau lihat teks di bawah")
        # Teks tree sebagai fallback
        st.subheader("Struktur Tree (Text)")
        tree_text = get_tree_text(1, st.session_state.members)
        st.code("\n".join(tree_text), language="text")

if __name__ == "__main__":
    main()
