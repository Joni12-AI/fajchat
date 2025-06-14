
// FINAL chatbot-widget.js – Merged old + new functionality (FAJ Integration)

document.addEventListener('DOMContentLoaded', function () {
    const chatbotWidget = document.getElementById('chatbotWidget');
    const chatbotButton = document.getElementById('chatbotButton');
    const chatbotContent = document.getElementById('chatbotContent');
    const registrationForm = document.getElementById('registrationForm');
    const chatInterface = document.getElementById('chatInterface');
    const userForm = document.getElementById('userForm');
    const chatMessages = document.getElementById('chatMessages');
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');

    const menuToggle = document.getElementById('menuToggle');
    const actionMenu = document.getElementById('actionMenu');
    const newChatBtn = document.getElementById('newChatBtn');
    const downloadChatBtn = document.getElementById('downloadChatBtn');
    const closeChatBtn = document.getElementById('closeChat');

    // Toggle Chat Open/Close
    chatbotButton.addEventListener('click', function () {
        chatbotContent.style.display = chatbotContent.style.display === 'flex' ? 'none' : 'flex';
        chatbotContent.style.animation = 'fadeIn 0.3s ease';
        actionMenu.classList.remove('show');
    });

    menuToggle.addEventListener('click', function (e) {
        e.stopPropagation();
        actionMenu.classList.toggle('show');
        if (actionMenu.classList.contains('show')) {
            document.addEventListener('click', closeMenuOutside);
        }
    });

    function closeMenuOutside(e) {
        if (!e.target.closest('.header-actions')) {
            actionMenu.classList.remove('show');
            document.removeEventListener('click', closeMenuOutside);
        }
    }

    newChatBtn.addEventListener('click', function () {
        actionMenu.classList.remove('show');
        if (confirm('Are you sure you want to start a new chat?')) {
            fetch('/reset', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        window.location.reload();
                    }
                });
        }
    });

    closeChatBtn.addEventListener('click', function () {
        actionMenu.classList.remove('show');
        chatbotContent.style.display = 'none';
    });

    downloadChatBtn.addEventListener('click', function () {
        fetch('/download_chat', {
            method: 'GET',
            credentials: 'same-origin'
        })
            .then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'chat_history.pdf';
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            });
    });

    // Phone validation (intl-tel-input)
    const phoneInput = document.getElementById('phone');
    const iti = window.intlTelInput(phoneInput, {
        preferredCountries: ["ae", "us", "gb", "pk", "in"],
        separateDialCode: true,
        utilsScript: "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.19/js/utils.js"
    });

    // Form Submit → Trigger categories
    userForm.addEventListener('submit', function (e) {
        e.preventDefault();

        let valid = true;
        const firstName = document.getElementById('first_name');
        const lastName = document.getElementById('last_name');
        const email = document.getElementById('email');

        if (!firstName.value.trim()) {
            document.getElementById('first_name_error').style.display = 'block';
            valid = false;
        } else {
            document.getElementById('first_name_error').style.display = 'none';
        }

        if (!lastName.value.trim()) {
            document.getElementById('last_name_error').style.display = 'block';
            valid = false;
        } else {
            document.getElementById('last_name_error').style.display = 'none';
        }

        if (!phoneInput.value.trim() || !iti.isValidNumber()) {
            document.getElementById('phone_error').style.display = 'block';
            valid = false;
        } else {
            document.getElementById('phone_error').style.display = 'none';
        }

        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!email.value.trim() || !emailRegex.test(email.value)) {
            document.getElementById('email_error').style.display = 'block';
            valid = false;
        } else {
            document.getElementById('email_error').style.display = 'none';
        }

        if (!valid) return;

        const formData = new FormData(userForm);

        fetch('/user_form', {
            method: 'POST',
            body: formData
        })
            .then(() => {
                registrationForm.style.display = 'none';
                chatInterface.style.display = 'flex';
                fetch('/') // Trigger initial categories
                    .then(res => res.text())
                    .then(html => updateChatMessages(html));
            })
            .catch(err => console.error('Form error:', err));
    });

    function sendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;

        const formData = new FormData();
        formData.append('message', message);

        fetch('/', {
            method: 'POST',
            body: formData,
            credentials: 'include'
        })
            .then(res => res.text())
            .then(html => {
                messageInput.value = '';
                updateChatMessages(html);
            });
    }

    function updateChatMessages(html) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const messages = doc.querySelectorAll('.message, .date-header');

        if (chatMessages) {
            chatMessages.innerHTML = '';
            messages.forEach(msg => {
                const cloned = msg.cloneNode(true);
                chatMessages.appendChild(cloned);

                // Enable input if bot asks a follow-up
                if (
                    cloned.classList.contains('bot-message') &&
                    cloned.textContent.toLowerCase().includes('how can we help')
                ) {
                    enableInput();
                }
            });
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    function enableInput() {
        if (messageInput && sendButton) {
            messageInput.disabled = false;
            sendButton.disabled = false;
            messageInput.placeholder = "Type your message...";
            messageInput.focus();
        }
    }

    function sendCategory(category) {
        if (messageInput) {
            messageInput.value = category;
            sendMessage();
        }
    }

    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') sendMessage();
    });

    window.sendCategory = sendCategory;
});
// Close chat on outside click
document.addEventListener('click', function (event) {
    if (
        chatbotContent.style.display === 'flex' &&
        !chatbotContent.contains(event.target) &&
        !chatbotButton.contains(event.target) &&
        !actionMenu.contains(event.target)
    ) {
        chatbotContent.style.display = 'none';
        actionMenu.classList.remove('show');
    }
});

