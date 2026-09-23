// static/js/teacher.js
document.addEventListener("DOMContentLoaded", () => {
    if (typeof CLASS_ID === 'undefined') return;

    const dateInput = document.getElementById('class-date');
    if (dateInput) {
        dateInput.valueAsDate = new Date();
    }

    // Carrega alunos para fazer a chamada
    fetch(`/api/class/${CLASS_ID}/students`)
        .then(res => res.json())
        .then(students => {
            const tbody = document.querySelector('#students-table tbody');
            if (tbody) {
                tbody.innerHTML = students.map(s => `
                    <tr data-student-id="${s.id}">
                        <td style="font-weight: bold;">${s.name}</td>
                        <td>
                            <select class="status-select" style="padding: 5px; border-radius: 4px;">
                                <option value="presente">🟢 Presente</option>
                                <option value="ausente">🔴 Ausente</option>
                            </select>
                        </td>
                        <td><input type="number" class="grade-input" min="0" max="10" placeholder="0 a 10" style="width: 70px; padding: 5px;"></td>
                        <td>
                            <select class="hw-select" style="padding: 5px; border-radius: 4px;">
                                <option value="Sim">✅ Fez</option>
                                <option value="Nao">❌ Não Fez</option>
                            </select>
                        </td>
                        <td><input type="text" class="comments-input" placeholder="Comportamento..." style="width: 100%; padding: 5px; box-sizing: border-box;"></td>
                    </tr>
                `).join('');
            }
        });

    // Carrega o histórico inicial
    loadHistory();
});

// A função saveRecords deve ficar solta (fora do DOMContentLoaded) para poder ser chamada no botão HTML
function saveRecords() {
    const date = document.getElementById('class-date').value;
    const topic = document.getElementById('class-topic').value || 'Sem tema registrado';
    if(!date) return alert("Por favor, selecione a data.");

    const records = Array.from(document.querySelectorAll('#students-table tbody tr')).map(tr => ({
        student_id: tr.dataset.studentId,
        status: tr.querySelector('.status-select').value,
        grade: tr.querySelector('.grade-input').value || null,
        homework: tr.querySelector('.hw-select').value,
        comments: tr.querySelector('.comments-input').value
    }));

    fetch('/api/save_records', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ class_id: CLASS_ID, date: date, topic: topic, records: records })
    }).then(() => {
        alert('Registros salvos com sucesso!');
        loadHistory();
    });
}

function loadHistory() {
    if (typeof CLASS_ID === 'undefined') return;

    fetch(`/api/class/${CLASS_ID}/history`)
        .then(res => res.json())
        .then(data => {
            const container = document.getElementById('history-container');
            if (!container) return;
            
            if(Object.keys(data).length === 0) {
                container.innerHTML = "<p style='color: #64748b;'>Nenhum histórico registrado.</p>";
                return;
            }

            let html = '';
            for (const [date, info] of Object.entries(data)) {
                const dateObj = new Date(date + 'T00:00:00');
                const dateFormatted = dateObj.toLocaleDateString('pt-BR');

                html += `<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 1rem; padding: 1rem;">
                    <h4 style="margin-top: 0; color: #1e293b; border-bottom: 1px solid #cbd5e1; padding-bottom: 5px;">📅 ${dateFormatted} - ${info.topic}</h4>
                    <table class="table-list" style="margin-top: 10px;">
                        <thead><tr><th>Aluno</th><th>Status</th><th>Nota</th><th>HW</th><th>Obs</th></tr></thead>
                        <tbody>
                            ${info.records.map(r => `
                                <tr>
                                    <td>${r.student_name}</td>
                                    <td><span style="color: ${r.status === 'presente' ? '#10b981' : '#ef4444'}; font-weight: bold;">${r.status.toUpperCase()}</span></td>
                                    <td>${r.grade !== null ? r.grade : '-'}</td>
                                    <td>${r.homework}</td>
                                    <td><small>${r.comments || '-'}</small></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>`;
            }
            container.innerHTML = html;
        });
}