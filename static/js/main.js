// Shared utility functions across pages
function getSessionData() {
    return {
        file_id: sessionStorage.getItem('file_id'),
        headers: JSON.parse(sessionStorage.getItem('headers') || '[]'),
        target_table: sessionStorage.getItem('target_table'),
        mapping: JSON.parse(sessionStorage.getItem('mapping') || '{}'),
        validation: JSON.parse(sessionStorage.getItem('validation') || 'null'),
        result: JSON.parse(sessionStorage.getItem('result') || 'null')
    };
}

function checkWorkflowState(requiredKeys) {
    const data = getSessionData();
    for (const key of requiredKeys) {
        const val = data[key];
        if (val === null || val === undefined || val === '') {
            alert('Akses tidak valid. Silakan mulai dari Upload Excel.');
            window.location.href = '/import';
            return false;
        }
        if (Array.isArray(val) && val.length === 0) {
            alert('Akses tidak valid. Silakan mulai dari Upload Excel.');
            window.location.href = '/import';
            return false;
        }
        if (typeof val === 'object' && !Array.isArray(val) && Object.keys(val).length === 0) {
            alert('Akses tidak valid. Silakan mulai dari Upload Excel.');
            window.location.href = '/import';
            return false;
        }
    }
    return true;
}
