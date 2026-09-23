// static/js/parent.js
document.addEventListener("DOMContentLoaded", () => {
    fetch('/api/my-records')
        .then(res => {
            if(!res.ok) throw new Error('Dados não encontrados');
            return res.json();
        })
        .then(data => {
            const content = document.getElementById('app-content');
            
            let html = `
                <div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: var(--shadow); margin-bottom: 2rem; border-left: 5px solid #10b981;">
                    <h2 style="margin: 0 0 5px 0; color: #1e293b;">🎓 ${data.student_name}</h2>
                    <p style="margin: 0; color: #64748b;">Turma: <b>${data.class_name}</b> | Prof: <b>${data.teacher_name}</b></p>
                </div>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin-bottom: 2rem;">
                    <div class="stat-box">
                        <div class="stat-label">Média das Notas</div>
                        <div class="stat-value">${data.stats.average}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Frequência</div>
                        <div class="stat-value" style="color: ${data.stats.frequency >= 75 ? '#10b981' : '#ef4444'}">${data.stats.frequency}%</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Faltas Acumuladas</div>
                        <div class="stat-value" style="color: #ef4444;">${data.stats.absences}</div>
                    </div>
                </div>

                <div class="card">
                    <div class="section-title">Histórico Detalhado (Aulas)</div>
                    ${data.records.length > 0 ? `
                    <table class="table-list">
                        <thead>
                            <tr>
                                <th>Data</th>
                                <th>Conteúdo Visto</th>
                                <th>Presença</th>
                                <th>Lição de Casa</th>
                                <th>Nota</th>
                                <th>Comentário do Prof.</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.records.map(r => {
                                const dateObj = new Date(r.record_date + 'T00:00:00');
                                return `
                                <tr>
                                    <td><strong>${dateObj.toLocaleDateString('pt-BR')}</strong></td>
                                    <td>${r.topic || '-'}</td>
                                    <td>
                                        ${r.status === 'presente' 
                                            ? '<span style="color:#10b981; font-weight:bold;">Presente</span>' 
                                            : '<span style="color:#ef4444; font-weight:bold;">Falta</span>'}
                                    </td>
                                    <td>${r.homework}</td>
                                    <td><strong>${r.grade !== null ? r.grade : '-'}</strong></td>
                                    <td><small>${r.comments || ''}</small></td>
                                </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                    ` : '<p style="color: #64748b;">Nenhuma aula registrada ainda.</p>'}
                </div>
            `;
            content.innerHTML = html;
        })
        .catch(err => {
            const content = document.getElementById('app-content');
            if (content) {
                content.innerHTML = `
                    <div class="card" style="text-align: center; color: #ef4444; padding: 3rem;">
                        <h2>Conta sem vínculo ativo</h2>
                        <p>Não encontramos nenhum aluno matriculado para este login no semestre atual.</p>
                        <p>Por favor, contate a secretaria da escola.</p>
                    </div>
                `;
            }
        });
});