import streamlit as st
from collections import deque
import pandas as pd
from datetime import datetime

# ---------------------------- Data Model ----------------------------
class Member:
    def __init__(self, id, name, sponsor_id, parent_id=None, is_active=False):
        self.id = id
        self.name = name
        self.sponsor_id = sponsor_id          # untuk Auto Rich (referral)
        self.parent_id = parent_id            # untuk Auto Cuan (placement)
        self.left_child_id = None
        self.right_child_id = None
        self.is_active = is_active
        self.balance_cuan = 0
        self.balance_rich = 0
        self.total_spent = 0
        self.total_commission_received = 0

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
        # Antrian untuk spillover round‑robin: berisi node yang masih punya slot kosong
        st.session_state.placement_queue = deque([1])
        st.session_state.selected_sponsor_id = 1
        st.session_state.reg_name = ""
        # Konfigurasi komisi default
        st.session_state.cuan_percent = [0, 0.01, 0.01, 0.05, 0.03, 0.03, 0.02, 0.03, 0.07]
        st.session_state.rich_percent = [0, 0.05, 0.05, 0.04, 0.04, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01]
        st.session_state.cuan_max_level = 8
        st.session_state.rich_max_level = 10
        st.session_state.sponsor_bonus_percent = 0.20
        st.session_state.min_spend_active = 100000

def find_placement_cuan():
    """
    Round‑robin spillover dimulai dari kanan.
    Mengambil node pertama dari antrian yang masih memiliki slot kosong.
    Slot kanan diprioritaskan, jika penuh maka slot kiri.
    Setelah diisi, jika node masih memiliki slot lain, ia dikembalikan ke antrian.
    """
    members = st.session_state.members
    queue = st.session_state.placement_queue

    if not queue:
        # Jika antrian kosong, isi ulang dengan semua node yang memiliki slot kosong
        for node in members.values():
            if node.left_child_id is None or node.right_child_id is None:
                queue.append(node.id)

    node_id = queue.popleft()
    node = members[node_id]

    # Prioritas kanan
    if node.right_child_id is None:
        is_left = False          # akan menjadi anak kanan
        # Jika setelah diisi kanan, kiri masih kosong, maka node masih punya slot
        if node.left_child_id is None:
            queue.append(node_id)
        return node_id, is_left

    elif node.left_child_id is None:
        is_left = True           # akan menjadi anak kiri
        # Node menjadi penuh karena kanan sudah terisi, tidak dikembalikan
        return node_id, is_left

    else:
        # Seharusnya tidak sampai ke sini karena node penuh tidak masuk antrian
        return find_placement_cuan()

def register_member(sponsor_id, name):
    members = st.session_state.members
    if sponsor_id not in members:
        return None, f"Sponsor ID {sponsor_id} tidak ditemukan."
    for m in members.values():
        if m.name.lower() == name.lower():
            return None, f"Nama '{name}' sudah terdaftar."

    new_id = st.session_state.next_id
    st.session_state.next_id += 1

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

    # Node baru memiliki dua slot kosong, tambahkan ke antrian
    st.session_state.placement_queue.append(new_id)

    posisi = "kanan" if not is_left else "kiri"
    info = (f"✅ Auto Cuan: anak {posisi} dari {parent.name} (ID:{parent.id})\n"
            f"✅ Auto Rich: sponsor langsung = {members[sponsor_id].name} (ID:{sponsor_id})")
    return new_member, info

# ---------------------------- Fungsi komisi & lainnya (sama seperti sebelumnya) ----------------------------
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
                    anc.total_commission_received += komisi
                    st.session_state.total_bonus_cuan += komisi
                bonus_cuan += komisi
                breakdown_cuan.append((anc_id, anc.name, f"Matrix Level {lvl} ({percent*100:.0f}%)", komisi))
        # Jika anc tidak aktif -> komisi hangus, tetapi ancestor di atas tetap diproses

    sponsor_bonus_total = 0
    for anc_id, _, _, komisi in breakdown_cuan:
        if komisi > 0:
            sponsor_bonus_total += calculate_sponsor_bonus_chain(anc_id, komisi, members, st.session_state.sponsor_bonus_percent)

    return {
        'buyer_name': member.name,
        'buyer_id': member_id,
        'amount': amount,
        'member_active': member.is_active,
        'ancestors_cuan': ancestors,
        'bonus_cuan': bonus_cuan,
        'bonus_rich': 0,
        'total_bonus': bonus_cuan + sponsor_bonus_total,
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
    lines = ['digraph G {', '    rankdir=TB;', '    node [shape=box, style=filled, fillcolor=lightblue, fontname="Arial"];']
    lines.append('    margin=0;')
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
            lines.append(f'    "{nid}" -> "{node.left_child_id}";')
            queue.append(node.left_child_id)
        if node.right_child_id:
            lines.append(f'    "{nid}" -> "{node.right_child_id}";')
            queue.append(node.right_child_id)
    lines.append('}')
    return "\n".join(lines)

def get_member_tree_rich(root_id, members, search_id=None):
    descendants = get_descendants_rich(root_id, members)
    if not descendants:
        return ""
    lines = ['digraph G {', '    rankdir=TB;', '    node [shape=box, style=filled, fillcolor=lightblue, fontname="Arial"];']
    lines.append('    margin=0;')
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
            lines.append(f'    "{node.sponsor_id}" -> "{nid}";')
    lines.append('}')
    return "\n".join(lines)

def create_sample_network():
    members = st.session_state.members
    if len(members) > 1:
        st.warning("Jaringan sudah memiliki member. Reset terlebih dahulu.")
        return
    sample_data = [
        (1, "Member 1"), (1, "Member 2"),
        (2, "Member 3"), (2, "Member 4"),
        (3, "Member 5"), (3, "Member 6"),
        (4, "Member 7"), (4, "Member 8"),
        (5, "Member 9"), (5, "Member 10"),
    ]
    for sponsor_id, name in sample_data:
        new, info = register_member(sponsor_id, name)
        if new:
            st.success(f"{name} (ID:{new.id}) berhasil.")
        else:
            st.error(f"Gagal: {info}")
    st.info("Sample jaringan 10 member selesai. Semua member dalam status ACTIVE.")

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
    st.markdown("**Auto Cuan** (belanja ≥ Rp100.000 untuk status aktif) | **Auto Rich** (belanja bebas)")

    init_session()

    with st.sidebar:
        st.header("🛠️ Manajemen")
        if st.button("🌳 Sample Jaringan 10 Member", use_container_width=True):
            create_sample_network()
        if st.button("🗑️ Reset Aplikasi", use_container_width=True):
            reset_app()
        st.markdown("---")
        st.header("⚙️ Pengaturan Komisi (Auto Cuan)")
        st.session_state.min_spend_active = st.number_input("Minimal belanja untuk status aktif", min_value=0, value=100000, step=10000)
        st.session_state.sponsor_bonus_percent = st.number_input("Bonus sponsor (%)", min_value=0.0, max_value=1.0, value=0.20, step=0.01, format="%.2f")
        st.write("Persentase komisi matrix per level (1-8):")
        cols = st.columns(4)
        for i in range(1, 9):
            col = cols[(i-1)%4]
            default = [0,1,1,5,3,3,2,3,7][i]
            val = col.number_input(f"Level {i} (%)", min_value=0, max_value=100, value=default, step=1, key=f"cuan_lvl_{i}")
            st.session_state.cuan_percent[i] = val / 100.0
        st.header("⚙️ Pengaturan Komisi (Auto Rich)")
        st.write("Persentase komisi per level (1-10):")
        cols2 = st.columns(5)
        defaults_rich = [0,5,5,4,4,2,1,1,1,1,1]
        for i in range(1, 11):
            col = cols2[(i-1)%5]
            val = col.number_input(f"L{i} (%)", min_value=0, max_value=100, value=defaults_rich[i], step=1, key=f"rich_lvl_{i}")
            st.session_state.rich_percent[i] = val / 100.0
        st.markdown("---")
        st.header("📊 Ringkasan Cepat")
        total_member = len(st.session_state.members)
        total_cash_in = st.session_state.total_cash_in
        total_bonus = st.session_state.total_bonus_cuan + st.session_state.total_bonus_rich + st.session_state.total_sponsor_bonus
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
        col4.metric("Komisi Auto Cuan (Matrix)", f"Rp{st.session_state.total_bonus_cuan:,.0f}")
        col5.metric("Bonus Sponsor Auto Cuan", f"Rp{st.session_state.total_sponsor_bonus:,.0f}")
        col6.metric("Komisi Auto Rich", f"Rp{st.session_state.total_bonus_rich:,.0f}")
        nett = st.session_state.total_cash_in - (st.session_state.total_bonus_cuan + st.session_state.total_bonus_rich + st.session_state.total_sponsor_bonus)
        st.metric("Nett Perusahaan", f"Rp{nett:,.0f}")

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
                "Parent Cuan": m.parent_id, "Status Aktif": "✅" if m.is_active else "❌",
                "Komisi Cuan": m.balance_cuan, "Komisi Rich": m.balance_rich,
                "Total Belanja": m.total_spent
            })
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)

    with tab3:
        st.header("📝 Registrasi Member Baru")
        new_name = st.text_input("Nama Lengkap", value=st.session_state.reg_name)
        st.session_state.reg_name = new_name
        sponsor_list = [(m.id, f"{m.name} (ID:{m.id})") for m in st.session_state.members.values()]
        current_index = 0
        for i, (sid, _) in enumerate(sponsor_list):
            if sid == st.session_state.selected_sponsor_id:
                current_index = i
                break
        selected_sponsor = st.selectbox("Pilih Sponsor (Auto Rich)", options=sponsor_list, format_func=lambda x: x[1], index=current_index)
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
