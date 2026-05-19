// Drag & drop upload
document.querySelectorAll('.upload-box').forEach(box => {
  const input = box.querySelector('input[type="file"]');
  box.addEventListener('click', () => input && input.click());
  box.addEventListener('dragover', e => { e.preventDefault(); box.classList.add('drag-over'); });
  box.addEventListener('dragleave', () => box.classList.remove('drag-over'));
  box.addEventListener('drop', e => {
    e.preventDefault(); box.classList.remove('drag-over');
    if (input && e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
});

// File name preview on select
document.querySelectorAll('input[type="file"]').forEach(inp => {
  inp.addEventListener('change', () => {
    const box = inp.closest('.upload-box');
    if (!box) return;
    const p = box.querySelector('p');
    if (p && inp.files.length) p.textContent = inp.files[0].name;
  });
});

// Format radio list selection highlight
document.querySelectorAll('.format-item').forEach(item => {
  item.addEventListener('click', () => {
    item.closest('.format-list').querySelectorAll('.format-item').forEach(i => i.classList.remove('selected'));
    item.classList.add('selected');
    const radio = item.querySelector('input[type="radio"]');
    if (radio) radio.checked = true;
  });
});

// Auto-dismiss alerts
document.querySelectorAll('.alert').forEach(alert => {
  setTimeout(() => { alert.style.opacity = '0'; alert.style.transition = 'opacity .4s'; setTimeout(() => alert.remove(), 400); }, 4000);
});
