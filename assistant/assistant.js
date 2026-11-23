// Pembantu PERKESO: scheme finder + claim guide (fixed rules) with AI checklist (/api/checklist), AI chat (/api/chat),
// contribution calculator (/api/caruman); plus an in-page bar that explains the current page (/api/explain).
(() => {
  const P = "https://www.perkeso.gov.my/perkhidmatan-kami/";

  // ---- 1. Scheme finder: plain decision tree, no AI needed ----
  const TREE = {
    start: { q: "Siapakah anda?", o: [
      ["Majikan", "r_majikan"], ["Pekerja bergaji", "pekerja"],
      ["Bekerja sendiri (cth. e-hailing, peniaga, petani)", "r_sendiri"], ["Suri rumah", "r_suri"],
      ["Saya mahu buat tuntutan / hilang kerja", "tuntut"]] },
    pekerja: { q: "Status anda sebagai pekerja?", o: [
      ["Warganegara / Penduduk Tetap", "r_tempatan"], ["Pekerja asing", "r_asing"], ["Pembantu rumah (pekerja domestik)", "r_domestik"]] },
  };
  const R = {
    r_majikan: { t: "Pendaftaran & caruman majikan", tag: "Akta 4 · Akta 800",
      d: ["Daftar syarikat dan pekerja dengan PERKESO.", "Bayar caruman bulanan melalui Portal ASSIST.", "Semak kadar caruman dengan kalkulator di tab Kalkulator."],
      l: [["Pendaftaran Majikan", P + "majikan-pekerja/pendaftaran-majikan"], ["Kadar Caruman", P + "majikan-pekerja/kadar-caruman.html"], ["Portal ASSIST", "https://assist.perkeso.gov.my/employer/login"]],
      ask: "Saya majikan baru. Apakah langkah untuk mendaftar dengan PERKESO dan bila tarikh akhir bayar caruman?" },
    r_tempatan: { t: "LINDUNG Pekerja + LINDUNG Kerjaya", tag: "Skim Bencana Pekerjaan · Skim Keilatan · SIP",
      d: ["Majikan anda wajib mendaftar dan mencarum untuk anda (kongsi caruman: anda ~0.7% gaji, majikan ~1.95%).",
        "Melindungi kemalangan kerja & perjalanan, hilang upaya, kematian, dan hilang pekerjaan (SIP, umur 18–60).",
        "Pilihan: LINDUNG 24 Jam (sukarela) untuk kemalangan di luar waktu kerja.",
        "Umur 60 tahun ke atas: Skim Bencana Pekerjaan sahaja, dibayar majikan."],
      l: [["Pekerja Bermajikan", P + "perlindungan/pekerja-bermajikan.html"], ["LINDUNG 24 Jam", P + "perlindungan/lindung-24-jam.html"], ["Insurans Pekerjaan", P + "perlindungan/insurans-pekerjaan.html"]],
      ask: "Saya pekerja bergaji. Apakah perlindungan yang saya dapat dan berapa caruman yang dipotong dari gaji saya?" },
    r_asing: { t: "LINDUNG Pekerja (Pekerja Asing)", tag: "Skim Bencana Kerja · Skim Keilatan · LINDUNG 24 Jam",
      d: ["Majikan wajib mendaftar dan mencarum; perlu pasport dan pas kerja yang sah.",
        "Melindungi kemalangan kerja, hilang upaya/kematian, dan kemalangan di luar waktu kerja (LINDUNG 24 Jam, wajib sejak 1 Jun 2026).",
        "Tidak termasuk Insurans Pekerjaan (SIP)."],
      l: [["Pekerja Asing", P + "perlindungan/pekerja-asing.html"]],
      ask: "What SOCSO protection do foreign workers get and who pays the contribution?" },
    r_domestik: { t: "LINDUNG Pekerja (Pekerja Domestik)", tag: "Sama seperti pekerja formal",
      d: ["Majikan (isi rumah) wajib mendaftar pembantu rumah dengan PERKESO.",
        "Pembantu tempatan: perlindungan sama seperti pekerja tempatan (termasuk SIP). Pembantu asing: sama seperti pekerja asing.",
        "Bayar bulanan melalui Portal ASSIST, atau pendahuluan sehingga 24 bulan melalui aplikasi Prihatin."],
      l: [["Pekerja Domestik", P + "perlindungan/pekerja-domestik.html"], ["Portal ASSIST", "https://assist.perkeso.gov.my/employer/login"]],
      ask: "Saya ada pembantu rumah. Bagaimana cara daftar dan berapa caruman?" },
    r_sendiri: { t: "LINDUNG Kendiri", tag: "Akta 789 · RM13.10–RM49.40 sebulan",
      d: ["Wajib untuk pemandu teksi, e-hailing dan bas; terbuka kepada 19 sektor lain (cth. peniaga, petani, nelayan).",
        "Pilih pelan ikut pendapatan: RM13.10, RM19.40, RM36.90 atau RM49.40 sebulan.",
        "Daftar dan bayar sendiri melalui Web/Aplikasi Prihatin."],
      l: [["Pekerjaan Sendiri", P + "perlindungan/pekerjaan-sendiri.html"], ["Portal Prihatin", "https://prihatin.perkeso.gov.my/"]],
      ask: "Saya pemandu e-hailing. Bagaimana nak mencarum PERKESO dan berapa kosnya?" },
    r_suri: { t: "LINDUNG Kasih", tag: "Akta 838 · RM120 setahun",
      d: ["Perlindungan bencana domestik untuk suri rumah (isteri, ibu, janda, balu, ibu tunggal).",
        "Caruman RM120 untuk 12 bulan, dibayar terlebih dahulu oleh suami, suri rumah sendiri, keluarga atau pihak ketiga.", "Daftar melalui Portal Suri."],
      l: [["Suri Rumah", P + "perlindungan/suri-rumah.html"], ["Portal Suri", "https://suri.perkeso.gov.my/"]],
      ask: "Saya suri rumah. Siapa yang layak untuk LINDUNG Kasih dan bagaimana cara mendaftar?" },
  };

  // ---- 2. Claim guide: facts from permohonan-faedah, skim-bencana-pekerjaan, skim-keilatan, insurans-pekerjaan, lindung-24-jam ----
  const S = "https://www.perkeso.gov.my", F = S + "/images/borang/";
  const B34 = ["Borang 34", F + "Borang34/29062026-BORANG_34_BM.pdf"], SS34 = ["Senarai Semak Borang 34", F + "2024/091224-SS-DokumenBorang34.pdf"];
  const LF = ["Portal LINDUNG FAEDAH", "https://lindungfaedah.perkeso.gov.my/"], PF = ["Permohonan Faedah", P + "perlindungan/permohonan-faedah.html"];
  const kaunter = "Hantar borang dan dokumen sokongan di kaunter pejabat PERKESO berdekatan untuk semakan pegawai.";
  const viaForms = (notis) => [notis ? `Buat ${notis} melalui Portal LINDUNG FAEDAH, atau muat turun borang di bawah.` : "Muat turun borang di bawah.",
    "Lengkapkan bahagian pemohon dan sediakan dokumen sokongan dalam senarai semak.", kaunter];
  const CT = {
    start: { q: "Apa yang berlaku?", o: [
      ["Kemalangan semasa bekerja atau dalam perjalanan kerja", "kerja"],
      ["Penyakit akibat pekerjaan (cth. pekak kerana bising, asma)", "c_pk"],
      ["Kemalangan di luar waktu kerja", "c_l24"],
      ["Hilang upaya kekal / uzur teruk (bukan kerana kerja)", "c_ilat"],
      ["Pencarum meninggal dunia", "mati"], ["Saya hilang pekerjaan", "c_sip"],
      ["Saya bekerja sendiri dan ditimpa bencana kerja", "c_sps"], ["Suri rumah ditimpa bencana", "c_suri"],
      ["Saya pekerja asing", "c_asing"]] },
    kerja: { q: "Keadaan anda sekarang?", o: [["Cuti sakit / masih dirawat", "c_hus"], ["Hilang upaya kekal selepas rawatan", "c_huk"]] },
    mati: { q: "Punca kematian?", o: [["Kemalangan kerja / penyakit khidmat", "c_fot"], ["Sebab lain (sakit, kemalangan bukan kerja)", "c_penakat"]] },
  };
  const CR = {
    c_hus: { t: "Faedah Hilang Upaya Sementara (HUS)", tag: "Skim Bencana Pekerjaan",
      layak: ["Kemalangan semasa bekerja, dalam perjalanan antara rumah dan tempat kerja, atau ke tempat makan waktu rehat.", "Cuti sakit disahkan doktor sekurang-kurangnya 4 hari termasuk hari kemalangan."],
      faedah: ["Rawatan percuma di klinik panel PERKESO atau klinik/hospital Kerajaan sehingga pulih.", "80% gaji harian purata (RM30–RM158.67 sehari) sepanjang cuti sakit. Tidak dibayar bagi hari anda bekerja dan dibayar gaji."],
      langkah: viaForms("Notis Kemalangan"),
      borang: [["Panduan Mengisi Borang", F + "TuntutanFaedah2022/HUS/1-_Panduan_Mengisi_Borang_34.pdf"], SS34, B34, ["Kenyataan Butiran Gaji/Caruman", F + "TuntutanFaedah2022/HUS/4_-_PKSF1.pdf"]],
      l: [LF, ["Skim Bencana Pekerjaan", P + "perlindungan/skim-bencana-pekerjaan.html"]],
      ask: "Saya kemalangan semasa pergi kerja dan dapat cuti sakit. Bagaimana tuntut Faedah Hilang Upaya Sementara?" },
    c_huk: { t: "Faedah Hilang Upaya Kekal (HUK)", tag: "Skim Bencana Pekerjaan",
      layak: ["Hilang upaya kekal akibat kemalangan kerja atau penyakit khidmat; ditaksir oleh Jemaah Doktor."],
      tarikh: "Dalam tempoh 12 bulan dari tarikh terakhir hilang upaya sementara.",
      faedah: ["90% gaji harian purata (RM30–RM178.50 sehari).", "Taksiran 20% atau kurang: bayaran pukal. Lebih 20%: 1/5 dibayar pukal, baki bulanan sepanjang hayat.",
        "Elaun Layanan Sentiasa RM500 sebulan jika sentiasa memerlukan penjaga.", "Pemulihan jasmani/vokasional (fisioterapi, prostetik, kerusi roda, latihan)."],
      langkah: viaForms(),
      borang: [["Senarai Semak HUK", F + "TuntutanFaedah2022/HUK/Checklist_HUK_1.pdf"], ["Borang Permohonan FHUK", F + "2024/281025-BORANG_PERMOHONAN_FHUK.pdf"], ["Laporan Perubatan", F + "2024/091224-LaporanPerubatan-L1-BencanaKerja.pdf"]],
      l: [PF, ["Skim Bencana Pekerjaan", P + "perlindungan/skim-bencana-pekerjaan.html"]],
      ask: "Bagaimana Faedah Hilang Upaya Kekal dikira dan apa itu taksiran Jemaah Doktor?" },
    c_pk: { t: "Faedah Penyakit Khidmat", tag: "Skim Bencana Pekerjaan",
      layak: ["Penyakit berpunca daripada pekerjaan yang disenaraikan dalam Jadual Kelima Akta Keselamatan Sosial Pekerja 1969 (cth. hilang pendengaran akibat bunyi bising berterusan, asma akibat habuk/bahan kimia)."],
      faedah: ["Rawatan percuma di klinik panel PERKESO atau klinik/hospital Kerajaan.", "Faedah tunai sama seperti bencana pekerjaan (HUS / HUK)."],
      langkah: viaForms("Notis Penyakit Khidmat"),
      borang: [["Panduan Mengisi Borang", F + "TuntutanFaedah2022/PenyakitKhidmat/1_-_Panduan_Mengisi_Borang_34.pdf"], SS34, B34,
        ["Laporan Perubatan – Penyakit Khidmat", F + "2024/281025-LP-P.Khidmat-B2SPRM281025.pdf"], ["Kenyataan Butiran Gaji/Caruman", F + "TuntutanFaedah2022/PenyakitKhidmat/5_-_PKSF1.pdf"]],
      l: [LF, PF], ask: "Penyakit apa yang dikira penyakit khidmat dan bagaimana membuat tuntutan?" },
    c_l24: { t: "LINDUNG 24 Jam (Kemalangan Bukan Bencana Kerja)", tag: "Skim Kemalangan Bukan Bencana Kerja",
      layak: ["Pekerja yang dilindungi LINDUNG 24 Jam (wajib bagi pekerja asing, sukarela bagi warganegara) dan ditimpa kemalangan di luar waktu kerja."],
      tidak: ["Kemalangan di luar Malaysia.", "Keadaan akibat penyakit seperti kencing manis, demam atau darah tinggi.", "Pekerja asing yang menyalahgunakan pas/permit atau melanggar syarat kemasukan."],
      langkah: ["Mohon melalui Portal LINDUNG FAEDAH. Ikut 'Tatacara tuntutan faedah melalui Portal LINDUNG Faedah' di halaman LINDUNG 24 Jam."],
      l: [LF, ["LINDUNG 24 Jam", P + "perlindungan/lindung-24-jam.html"]],
      ask: "Saya kemalangan pada hujung minggu, bukan semasa kerja. Bolehkah saya tuntut LINDUNG 24 Jam?" },
    c_ilat: { t: "Pencen Ilat", tag: "Skim Keilatan",
      layak: ["Uzur kekal dan tidak mampu mencari nafkah sekurang-kurangnya 1/3 keupayaan pekerja normal; disahkan Jemaah Doktor.",
        "Belum berumur 60 tahun semasa Notis Keilatan diterima (atau uzur bermula sebelum 60).",
        "Caruman sekurang-kurangnya 24 bulan dalam 40 bulan berturut-turut, atau 2/3 bulan sejak mula mencarum (minimum 24 caruman)."],
      faedah: ["Pencen bulanan 50%–65% gaji bulanan purata, minimum RM550 sebulan, bermula dari tarikh Notis Keilatan diterima.",
        "Tidak cukup caruman: Bantuan Ilat, bayaran pukal sama dengan caruman Skim Keilatan berserta faedah.", "Elaun Layanan Sentiasa RM500 sebulan jika sentiasa memerlukan penjaga."],
      langkah: viaForms(),
      borang: [["Panduan Mengisi Borang", F + "TuntutanFaedah2022/PencenIlat/1_-_Panduan_Mengisi_Borang_34.pdf"], SS34, B34,
        ["Laporan Perubatan – Ilat", F + "2024/281025-LP-ILT-B2ILAT281025.pdf"], ["Borang A – Penyertaan Pembayaran", F + "TuntutanFaedah2022/PencenIlat/5_-_Borang_A_BKA1.pdf"]],
      l: [PF, ["Skim Keilatan", P + "perlindungan/skim-keilatan.html"]], ask: "Bagaimana saya tahu jika caruman saya cukup untuk Pencen Ilat?" },
    c_fot: { t: "Faedah Orang Tanggungan & Pengurusan Mayat", tag: "Skim Bencana Pekerjaan",
      layak: ["Pekerja meninggal dunia akibat kemalangan kerja atau penyakit khidmat."],
      faedah: ["Faedah Orang Tanggungan: 90% gaji harian purata (RM30–RM178.50 sehari). Balu/duda 3/5 seumur hidup; anak 2/5 sehingga 21 tahun atau berkahwin (atau ijazah pertama).",
        "Tiada balu/duda/anak: ibu bapa (4/10), adik-beradik (3/10), atau datuk/nenek.", "Faedah Pengurusan Mayat: kos sebenar atau RM3,000, mana lebih rendah, berdasarkan resit.",
        "Faedah Pendidikan: pinjaman untuk anak tanggungan."],
      langkah: viaForms("Notis Kematian"), borang: [SS34, B34], nota: "Laman PERKESO tidak menyenaraikan borang khusus untuk faedah ini; sahkan dokumen di kaunter.",
      l: [LF, ["Skim Bencana Pekerjaan", P + "perlindungan/skim-bencana-pekerjaan.html"]],
      ask: "Suami saya meninggal dunia dalam kemalangan semasa bekerja. Apakah faedah untuk saya dan anak-anak?" },
    c_penakat: { t: "Pencen Penakat", tag: "Skim Keilatan",
      layak: ["Pencarum meninggal dunia sebelum umur 60 tahun dan memenuhi syarat caruman (24 bulan dalam 40 bulan berturut-turut, atau 2/3 bulan sejak mula mencarum).",
        "Atau meninggal dunia semasa menerima Pencen Ilat, tanpa mengira umur."],
      faedah: ["Pencen bulanan kepada orang tanggungan: 50%–65% gaji bulanan purata, minimum RM550 sebulan."],
      langkah: viaForms("Notis Kematian"),
      borang: [["Panduan Mengisi Borang", F + "TuntutanFaedah2022/PencenPenakat/1_-_Panduan_Mengisi_Borang_34.pdf"], SS34, B34,
        ["Borang A – Penyertaan Pembayaran", F + "TuntutanFaedah2022/PencenPenakat/5_-_Borang_A_BKA1.pdf"]],
      l: [LF, ["Skim Keilatan", P + "perlindungan/skim-keilatan.html"]], ask: "Bapa saya pencarum dan meninggal dunia kerana sakit. Bolehkah keluarga mohon Pencen Penakat?" },
    c_sip: { t: "LINDUNG Kerjaya (Faedah Kehilangan Pekerjaan)", tag: "Sistem Insurans Pekerjaan",
      tarikh: "Dalam tempoh 60 hari dari tarikh hilang pekerjaan.",
      layak: ["Cukup syarat caruman dan kini tidak bekerja.", "Termasuk: diberhentikan, VSS/MSS, penutupan kerana bencana alam atau bankrap, pembuangan kerja secara konstruktif, letak jawatan kerana gangguan seksual/ugutan."],
      faedah: ["Elaun Mencari Pekerjaan selama 3–6 bulan, ikut rekod caruman.", "Kehilangan kerja mulai 1 Okt 2026: Fi Latihan sehingga RM7,000, Elaun Latihan RM30 sehari, Elaun Bekerja Semula Awal 50% baki elaun.",
        "Elaun Bantuan Mobiliti jika kerja baharu 100 km atau lebih dari rumah."],
      langkah: ["Mohon melalui Portal LINDUNG Kerjaya.", "Daftar di MYFutureJobs untuk dipadankan dengan kekosongan jawatan.", "Hadiri sesi bersama Pegawai Perkhidmatan Pekerjaan (ESO) dan latihan jika dirujuk."],
      l: [["Portal LINDUNG Kerjaya", "https://lindungkerjaya.perkeso.gov.my/"], ["MYFutureJobs", "https://myfuturejobs.gov.my/"], ["Insurans Pekerjaan", P + "perlindungan/insurans-pekerjaan.html"]],
      ask: "Saya diberhentikan kerja. Adakah saya layak Faedah Kehilangan Pekerjaan dan berapa lama elaun dibayar?" },
    c_sps: { t: "Faedah Skim Pekerjaan Sendiri", tag: "LINDUNG Kendiri · Akta 789",
      layak: ["Pencarum LINDUNG Kendiri yang ditimpa bencana semasa menjalankan pekerjaan sendiri."],
      langkah: ["Muat turun borang dan senarai semak di bawah.", "Lengkapkan borang dan sediakan dokumen sokongan.", "Hantar ke pejabat PERKESO terdekat."],
      borang: [["Senarai Semak SPS", F + "2024/091224_-SS-BORANG_PS2-NotisDanTuntutanFaedahPekerjaanSendiri.pdf"], ["Borang Tuntutan Faedah SPS", F + "TuntutanFaedah2022/SPS/2_-_Borang_Tuntutan_Faedah_SPS.pdf"]],
      l: [PF, ["Pekerjaan Sendiri", P + "perlindungan/pekerjaan-sendiri.html"]], ask: "Saya pemandu e-hailing dan kemalangan semasa bawa penumpang. Apa faedah yang boleh saya tuntut?" },
    c_suri: { t: "Faedah LINDUNG Kasih (Suri Rumah)", tag: "Akta 838",
      layak: ["Suri rumah berdaftar LINDUNG Kasih yang ditimpa bencana domestik."],
      langkah: ["Muat turun borang SR6 dan senarai semak.", "Lengkapkan borang dan sediakan dokumen sokongan.", kaunter],
      borang: [["Senarai Semak", F + "2024/091224_-SS_BORANG_SR6-NotisDanTuntutanFaedahSuriRumah.pdf"], ["Borang Tuntutan Faedah (SR6)", S + "/images/skssr/dokumen/BORANG_SR_6_-_BORANG_TUNTUTAN_SKSSR.pdf"]],
      l: [PF, ["Suri Rumah", P + "perlindungan/suri-rumah.html"]], ask: "Isteri saya cedera semasa memasak di rumah. Bagaimana tuntut LINDUNG Kasih?" },
    c_asing: { t: "Faedah Pekerja Asing", tag: "Borang 34-PA",
      layak: ["Pekerja asing berdaftar dengan pas/permit kerja yang sah."],
      langkah: ["Muat turun Borang 34-PA dan senarai semak.", "Majikan dan pekerja lengkapkan borang serta sediakan dokumen sokongan.", kaunter],
      borang: [["Senarai Semak 34-PA", S + "/images/pekerja_asing/bm/borang/100725-SENARAI_SEMAK-BORANG_34-PEKERJA_ASINGBORANG_BUTIRAN_NOTIS_DAN_TUNTUTAN_FAEDAH_PEKERJA_ASING_34-PA.pdf"], ["Borang 34-PA", F + "Borang34/290626-BORANG_34-PA.pdf"]],
      l: [PF, ["Pekerja Asing", P + "perlindungan/pekerja-asing.html"]], ask: "How does a foreign worker claim SOCSO benefits after an accident?" },
  };
  // Monthly benefit payment dates (tarikh-bayaran-faedah). ponytail: 2026 only, update yearly with the published table.
  const PAY = ["2026-01-30", "2026-02-11", "2026-03-16", "2026-04-20", "2026-05-22", "2026-07-01", "2026-07-31", "2026-09-01", "2026-10-01", "2026-10-30", "2026-12-01", "2026-12-21"];

  const h = (tag, attrs = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) k.startsWith("on") ? e.addEventListener(k.slice(2), v) : e.setAttribute(k, v);
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) e.append(c);
    return e;
  };
  const link = ([t, u]) => h("a", { href: u, target: "_blank", rel: "noopener" }, t);
  // Escape, then linkify URLs, **bold**, # headings and "[ ]" checkboxes; never inject raw model output as HTML.
  const render = (el, text) => {
    const esc = text.trimStart().replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
    el.innerHTML = esc.replace(/^#{1,4}\s*(.+)$/gm, "<b>$1</b>").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/\[ \]/g, "☐").replace(/https?:\/\/[^\s)<]+[^\s)<.,]/g, (u) => `<a href="${u}" target="_blank" rel="noopener">${u}</a>`);
  };
  // POST json, stream the plain-text reply into el. Returns the full text; throws on network/HTTP error.
  const streamTo = async (el, url, body, scroller = el) => {
    const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error(res.status);
    const reader = res.body.getReader(), dec = new TextDecoder();
    let text = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) return text;
      text += dec.decode(value, { stream: true }); render(el, text); scroller.scrollTop = scroller.scrollHeight;
    }
  };
  const printText = (title, text) => {
    const w = window.open("", "_blank");
    if (!w) return;
    w.document.title = title;
    w.document.body.append(Object.assign(w.document.createElement("h2"), { textContent: title }),
      Object.assign(w.document.createElement("pre"), { textContent: text, style: "white-space:pre-wrap;font:14px/1.5 sans-serif" }));
    w.print();
  };

  // ---- shell ----
  const fab = h("button", { id: "pk-fab", "aria-expanded": "false", "aria-controls": "pk-panel" }, "💬 Pembantu PERKESO");
  const views = { finder: h("div", { class: "pk-view on", id: "pk-finder" }), claim: h("div", { class: "pk-view", id: "pk-claim" }),
    chat: h("div", { class: "pk-view", id: "pk-chat" }), calc: h("div", { class: "pk-view", id: "pk-calc" }) };
  const tabs = h("div", { class: "pk-tabs", role: "tablist" });
  const setTab = (name) => {
    for (const [k, v] of Object.entries(views)) v.classList.toggle("on", k === name);
    for (const b of tabs.children) b.setAttribute("aria-selected", b.dataset.t === name);
    if (name === "chat") input.focus();
  };
  for (const [k, label] of [["finder", "Cari Skim"], ["claim", "Tuntutan"], ["chat", "Tanya"], ["calc", "Kalkulator"]]) {
    const b = h("button", { role: "tab", "aria-selected": k === "finder", onclick: () => setTab(k) }, label);
    b.dataset.t = k; tabs.append(b);
  }
  const panel = h("div", { id: "pk-panel", role: "dialog", "aria-label": "Pembantu PERKESO" },
    h("div", { class: "pk-head" }, h("b", {}, "Pembantu PERKESO"),
      h("button", { class: "pk-x", "aria-label": "Tutup", onclick: () => toggle(false) }, "×")),
    tabs, h("div", { class: "pk-body" }, Object.values(views)));
  const toggle = (open = !panel.classList.contains("open")) => {
    panel.classList.toggle("open", open); fab.setAttribute("aria-expanded", open);
  };
  fab.addEventListener("click", () => toggle());
  document.addEventListener("keydown", (e) => e.key === "Escape" && toggle(false));
  document.body.append(fab, panel);

  // ---- finder ----
  const showNode = (id) => {
    if (id === "tuntut") return setTab("claim");
    const v = views.finder; v.replaceChildren();
    if (TREE[id]) {
      v.append(h("p", { class: "pk-q" }, TREE[id].q),
        ...TREE[id].o.map(([t, next]) => h("button", { class: "pk-opt", onclick: () => showNode(next) }, t)));
      if (id !== "start") v.append(h("button", { class: "pk-btn ghost", onclick: () => showNode("start") }, "← Mula semula"));
      return;
    }
    const r = R[id];
    v.append(h("div", { class: "pk-card" }, h("span", { class: "pk-tag" }, r.tag), h("h3", {}, r.t),
      h("ul", {}, r.d.map((x) => h("li", {}, x))),
      h("div", { class: "pk-links" }, r.l.map((x, i) => [i ? " · " : "", link(x)])),
      h("div", { class: "pk-row" },
        h("button", { class: "pk-btn", onclick: () => { setTab("chat"); send(r.ask); } }, "Tanya lanjut"),
        h("button", { class: "pk-btn ghost", onclick: () => showNode("start") }, "Mula semula"))));
  };
  showNode("start");

  // ---- claim guide ----
  const sec = (title, items, Tag = "ul") => items?.length ? [h("h4", {}, title), h(Tag, {}, items.map((x) => h("li", {}, x)))] : null;
  const showClaim = (id) => {
    const v = views.claim; v.replaceChildren();
    if (CT[id]) {
      v.append(h("p", { class: "pk-q" }, CT[id].q), ...CT[id].o.map(([t, next]) => h("button", { class: "pk-opt", onclick: () => showClaim(next) }, t)));
      if (id !== "start") v.append(h("button", { class: "pk-btn ghost", onclick: () => showClaim("start") }, "← Mula semula"));
      return;
    }
    const r = CR[id], today = new Date().toISOString().slice(0, 10), next = PAY.find((d) => d >= today);
    const boxes = (r.borang || []).map(([t, u]) => h("label", { class: "pk-check" }, h("input", { type: "checkbox", onchange: tally }), " ", link([t, u])));
    const count = h("span", { class: "pk-count" });
    function tally() { count.textContent = ` (${boxes.filter((b) => b.firstChild.checked).length}/${boxes.length} sedia)`; }
    if (boxes.length) tally();
    v.append(h("div", { class: "pk-card" }, h("span", { class: "pk-tag" }, r.tag), h("h3", {}, r.t),
      r.tarikh && h("p", { class: "pk-due" }, "⏰ Tarikh akhir: " + r.tarikh),
      sec("Siapa layak", r.layak), sec("Tidak dilindungi", r.tidak), sec("Faedah", r.faedah), sec("Langkah", r.langkah, "ol"),
      boxes.length ? [h("h4", {}, "Borang", count), h("div", { class: "pk-checks" }, boxes)] : null,
      r.nota && h("p", { class: "pk-note" }, r.nota),
      next && r.faedah && id !== "c_sip" && h("p", { class: "pk-note" }, "Tarikh bayaran faedah bulanan seterusnya: " +
        new Date(next).toLocaleDateString("ms-MY", { day: "numeric", month: "long", year: "numeric" }) + ". ",
        link(["Jadual penuh", S + "/mengenai-kami/rujukan/tarikh-bayaran-faedah.html"])),
      h("div", { class: "pk-links" }, r.l.map((x, i) => [i ? " · " : "", link(x)])),
      personal(r),
      h("div", { class: "pk-row" },
        h("button", { class: "pk-btn", onclick: () => { setTab("chat"); send(r.ask); } }, "Tanya lanjut"),
        h("button", { class: "pk-btn ghost", onclick: () => showClaim("start") }, "Mula semula"))));
  };
  // AI checklist: the card's own facts + the user's situation -> tailored steps/documents (server forbids new forms).
  function personal(r) {
    const box = h("textarea", { rows: "3", maxlength: "1000", "aria-label": "Situasi anda",
      placeholder: "Ceritakan situasi anda, cth. 'Saya jatuh motor semasa pergi kerja 3 hari lepas, dapat MC 7 hari.' Jangan masukkan No. KP atau nama." });
    const out = h("div", { class: "pk-ai", "aria-live": "polite" });
    const print = h("button", { class: "pk-btn ghost", type: "button", hidden: "" }, "Cetak");
    const go = h("button", { class: "pk-btn", type: "submit" }, "Jana senarai semak");
    let text = "";
    print.addEventListener("click", () => printText("Senarai semak: " + r.t, text));
    return h("form", { class: "pk-personal", onsubmit: async (e) => {
        e.preventDefault();
        if (!box.value.trim() || go.disabled) return;
        go.disabled = true; print.hidden = true; out.textContent = "Menjana… (boleh ambil 20–40 saat)";
        const card = { ...r, borang: (r.borang || []).map(([t]) => t) };
        try { text = await streamTo(out, "/api/checklist", { card, situasi: box.value }); print.hidden = !text.trim(); }
        catch { out.textContent = "Maaf, tidak dapat menjana senarai semak sekarang. Sila cuba lagi."; }
        go.disabled = false;
      } },
      h("h4", {}, "Senarai semak peribadi ", h("span", { class: "pk-count" }, "(AI)")), box,
      h("div", { class: "pk-row" }, go, print), out,
      h("p", { class: "pk-note" }, "Dijana AI daripada maklumat kad ini. Sahkan dengan PERKESO sebelum menghantar tuntutan."));
  }
  showClaim("start");

  // ---- chat ----
  const history = [];
  const log = h("div", { class: "pk-log", "aria-live": "polite" });
  const input = h("input", { type: "text", placeholder: "Tanya apa-apa tentang PERKESO…", "aria-label": "Soalan anda", maxlength: "1000" });
  const sendBtn = h("button", { class: "pk-btn", type: "submit" }, "Hantar");
  const sugg = h("div", { class: "pk-sugg" }, [
    "Berapa caruman untuk gaji RM3,500?", "Saya kemalangan semasa pergi kerja, apa perlu buat?", "How do I register as a gig worker?",
  ].map((s) => h("button", { onclick: () => send(s) }, s)));
  async function send(q) {
    q = (q ?? input.value).trim();
    if (!q || sendBtn.disabled) return;
    input.value = ""; sugg.remove(); sendBtn.disabled = true;
    log.append(h("div", { class: "pk-msg user" }, q));
    const bot = h("div", { class: "pk-msg bot" }); log.append(bot);
    history.push({ role: "user", content: q });
    try {
      history.push({ role: "assistant", content: await streamTo(bot, "/api/chat", { messages: history }, log) });
    } catch (e) {
      history.pop(); bot.textContent = "Maaf, pembantu tidak dapat dihubungi sekarang. Sila cuba lagi.";
    }
    sendBtn.disabled = false; input.focus();
  }
  views.chat.append(log, sugg, h("form", { class: "pk-form", onsubmit: (e) => { e.preventDefault(); send(); } }, input, sendBtn));
  log.append(h("div", { class: "pk-msg bot" }, "Hai! Saya Pembantu PERKESO. Tanya saya tentang skim perlindungan, caruman, atau cara membuat tuntutan. Anda boleh tanya dalam Bahasa Melayu atau English."));

  // ---- page bar: AI plain-language explanation of THIS page, in the reader's language; sits in the page, not the panel ----
  const lang = h("select", { "aria-label": "Bahasa" }, [["ms", "Bahasa Melayu"], ["en", "English"], ["zh", "中文"], ["ta", "தமிழ்"],
    ["id", "Bahasa Indonesia"], ["bn", "বাংলা"], ["ne", "नेपाली"], ["my", "မြန်မာ"]].map(([v, t]) => h("option", { value: v }, t)));
  try { lang.value = localStorage.getItem("pk-lang") || "ms"; } catch {}
  const exOut = h("div", { class: "pk-ai", "aria-live": "polite" });
  const exGo = h("button", { class: "pk-btn", type: "submit" }, "Terangkan");
  const exHide = h("button", { class: "pk-btn ghost", type: "button", hidden: "", onclick: () => { exOut.replaceChildren(); exNote.hidden = exHide.hidden = true; } }, "Tutup");
  const exNote = h("p", { class: "pk-note", hidden: "" }, "Ringkasan dijana AI daripada kandungan laman ini. Rujuk teks asal di bawah untuk maklumat rasmi.");
  const bar = h("section", { id: "pk-bar", "aria-label": "Terangkan laman ini" },
    h("form", { onsubmit: async (e) => {
        e.preventDefault();
        if (exGo.disabled) return;
        try { localStorage.setItem("pk-lang", lang.value); } catch {}
        exGo.disabled = true; exHide.hidden = exNote.hidden = false; exOut.textContent = "Menjana… (boleh ambil 20–40 saat)";
        try { await streamTo(exOut, "/api/explain", { path: location.pathname, lang: lang.value }); }
        catch { exOut.textContent = "Maaf, tidak dapat menerangkan laman ini sekarang. Sila cuba lagi."; }
        exGo.disabled = false;
      } },
      h("span", { class: "pk-bar-t" }, "🌐 Faham laman ini dalam bahasa anda"), lang, exGo, exHide), exOut, exNote);
  // After the page's hero/slider (the fixed header covers anything above it); body top as a fallback.
  const hero = [...document.getElementById("tm-main")?.children || []].find((e) => e.offsetHeight > 0);
  hero ? hero.after(bar) : document.body.prepend(bar);

  // ---- calculator: arithmetic lives on the server (caruman.py), same function the chat uses ----
  const gaji = h("input", { type: "number", min: "0", step: "0.01", inputmode: "decimal", required: "", placeholder: "cth. 3500" });
  const kat = h("select", {}, h("option", { value: "tempatan" }, "Warganegara / PR (termasuk pembantu rumah tempatan)"), h("option", { value: "asing" }, "Pekerja asing (termasuk pembantu rumah asing)"));
  const tua = h("select", {}, h("option", { value: "" }, "Bawah 60 tahun"), h("option", { value: "1" }, "60 tahun ke atas"));
  const l24 = h("select", {}, h("option", { value: "" }, "Tidak menyertai"), h("option", { value: "1" }, "Menyertai (sukarela)"));
  const l24Field = h("label", { class: "pk-field" }, "LINDUNG 24 Jam", l24);
  kat.addEventListener("change", () => { l24Field.hidden = kat.value === "asing"; }); // mandatory for foreign workers
  const out = h("div", { "aria-live": "polite" });
  const rm = (n) => "RM" + n.toFixed(2);
  views.calc.append(h("form", { onsubmit: async (e) => {
      e.preventDefault();
      try {
        const res = await fetch("/api/caruman", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ gaji: +gaji.value, kategori: kat.value, umur_60_ke_atas: !!tua.value, lindung24: !!l24.value }) });
        if (!res.ok) throw new Error(res.status);
        const r = await res.json();
        out.replaceChildren(h("table", { class: "pk-table" },
          h("tr", {}, h("th", {}, "Skim"), h("th", {}, "Majikan"), h("th", {}, "Pekerja")),
          r.butiran.map((b) => h("tr", {}, h("td", {}, b.skim), h("td", {}, rm(b.majikan)), h("td", {}, rm(b.pekerja)))),
          h("tr", { class: "tot" }, h("td", {}, "Jumlah sebulan"), h("td", {}, rm(r.jumlah_majikan)), h("td", {}, rm(r.jumlah_pekerja)))),
          h("p", { class: "pk-note" }, r.nota));
      } catch { out.replaceChildren(h("p", { class: "pk-note" }, "Tidak dapat mengira. Sila semak input.")); }
    } },
    h("label", { class: "pk-field" }, "Gaji bulanan (RM)", gaji),
    h("label", { class: "pk-field" }, "Kategori pekerja", kat),
    h("label", { class: "pk-field" }, "Umur", tua), l24Field,
    h("button", { class: "pk-btn", type: "submit" }, "Kira caruman")), out);
})();
