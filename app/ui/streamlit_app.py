"""
app/ui/streamlit_app.py
Streamlit frontend — CV-first job matching
"""
import requests
import streamlit as st

API_URL = "http://api:8000"

st.set_page_config(
    page_title="Thai Job AI Agent",
    page_icon="🤖",
    layout="centered",
)

st.markdown("""
<style>
.job-card {
    background: #1e1e2e; color: #e0e0e0; border-radius: 12px; padding: 1.2rem;
    border-left: 4px solid #7c6ff7; margin: 12px 0;
}
.job-card strong { color: #ffffff; }
.skill-tag {
    background: #3730a3; color: #e0e7ff; border-radius: 4px;
    padding: 2px 8px; font-size: 12px; margin: 2px;
    display: inline-block;
}
.skill-tag.have {
    background: #065f46; color: #a7f3d0;
}
.skill-tag.missing {
    background: #7f1d1d; color: #fca5a5;
}
.score-badge {
    display: inline-block; padding: 4px 14px; border-radius: 20px;
    font-weight: bold; font-size: 15px; margin-bottom: 6px;
}
.score-high { background: #065f46; color: #a7f3d0; }
.score-mid  { background: #78350f; color: #fde68a; }
.score-low  { background: #7f1d1d; color: #fca5a5; }
.profile-box {
    background: #1e1e2e; color: #e0e0e0; border-radius: 12px;
    padding: 1.2rem; border-left: 4px solid #10b981; margin: 10px 0;
}
.profile-box strong { color: #ffffff; }
</style>
""", unsafe_allow_html=True)

# ─── HEADER ──────────────────────────────────────────────────
st.title("🤖 Thai Job Market AI Agent")
st.caption("อัพโหลด CV แล้ว AI จะวิเคราะห์และจับคู่งานที่เหมาะกับคุณ")

# ─── CV UPLOAD ───────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "📄 อัพโหลด CV ของคุณ (PDF)",
    type=["pdf"],
    help="รองรับทั้ง PDF แบบข้อความและแบบสแกน/ภาพ",
)

if uploaded_file is not None:
    st.info(f"📎 {uploaded_file.name} ({uploaded_file.size / 1024:.0f} KB)")

    if st.button("🤖 วิเคราะห์ CV และจับคู่งาน", use_container_width=True, type="primary"):
        with st.spinner("AI กำลังอ่านและวิเคราะห์ CV ของคุณ..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                resp = requests.post(f"{API_URL}/cv/analyze", files=files, timeout=90)
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.HTTPError as e:
                detail = ""
                try:
                    detail = e.response.json().get("detail", "")
                except Exception:
                    pass
                st.error(f"❌ {detail or e}")
                st.stop()
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.stop()

        # ─── PROFILE SUMMARY ────────────────────────────
        st.subheader("👤 โปรไฟล์ของคุณ")
        st.markdown(f'<div class="profile-box">{data.get("profile_summary", "")}</div>', unsafe_allow_html=True)

        # Skills found & missing
        col_have, col_miss = st.columns(2)
        with col_have:
            st.markdown("**✅ ทักษะที่มี**")
            skills_found = data.get("skills_found", [])
            if skills_found:
                st.markdown(
                    " ".join(f'<span class="skill-tag have">{s}</span>' for s in skills_found),
                    unsafe_allow_html=True,
                )
            else:
                st.caption("ไม่พบทักษะ")
        with col_miss:
            st.markdown("**❌ ทักษะที่ตลาดต้องการแต่ยังขาด**")
            skills_missing = data.get("skills_missing", [])
            if skills_missing:
                st.markdown(
                    " ".join(f'<span class="skill-tag missing">{s}</span>' for s in skills_missing),
                    unsafe_allow_html=True,
                )
            else:
                st.caption("ครบแล้ว!")

        # Recommendations
        recs = data.get("recommendations", "")
        if recs:
            st.markdown("**💡 คำแนะนำ**")
            st.markdown(f'<div class="profile-box">{recs}</div>', unsafe_allow_html=True)

        # ─── MATCHED JOBS ────────────────────────────────
        matched_jobs = data.get("matched_jobs", [])
        if matched_jobs:
            st.divider()
            st.subheader(f"💼 งานที่เหมาะกับคุณ ({len(matched_jobs)} ตำแหน่ง)")

            for j in matched_jobs:
                score = j.get("match_score", 0)
                if score >= 70:
                    score_class = "score-high"
                elif score >= 40:
                    score_class = "score-mid"
                else:
                    score_class = "score-low"

                sal = (
                    f"฿{j['salary_min']:,}–{j['salary_max']:,}"
                    if j.get("salary_min")
                    else "ไม่ระบุเงินเดือน"
                )

                reasons_html = ""
                match_reasons = j.get("match_reasons", [])
                if match_reasons:
                    reasons_html = "<br>".join(f"✅ {r}" for r in match_reasons)

                gap_html = ""
                gap_notes = j.get("gap_notes", [])
                if gap_notes:
                    gap_html = "<br>".join(f"⚠️ {g}" for g in gap_notes)

                job_url = j.get("url", "")
                link_html = (
                    f'<br><a href="{job_url}" target="_blank" style="color:#7c6ff7;font-weight:bold;">🔗 สมัครงานนี้</a>'
                    if job_url else ""
                )

                st.markdown(f"""
<div class="job-card">
<span class="score-badge {score_class}">Match {score}%</span><br>
<strong>{j.get('title','')}</strong> — {j.get('company','')}<br>
📍 {j.get('location','–')} &nbsp;|&nbsp; 💰 {sal}<br>
{''.join(f'<span class="skill-tag">{s}</span>' for s in j.get('skills', [])[:6])}
<br><br>
{reasons_html}
{"<br>" + gap_html if gap_html else ""}
{link_html}
</div>
""", unsafe_allow_html=True)

else:
    # Show placeholder when no file uploaded
    st.markdown("---")
    st.markdown(
        "<div style='text-align:center; padding:3rem; color:#888;'>"
        "<h3>📄 เริ่มต้นโดยอัพโหลด CV ของคุณ</h3>"
        "<p>AI จะวิเคราะห์ทักษะ จับคู่กับตำแหน่งงานจริงจาก JobsDB<br>"
        "และบอกว่าเหมาะกับงานไหน เพราะอะไร</p>"
        "</div>",
        unsafe_allow_html=True,
    )
