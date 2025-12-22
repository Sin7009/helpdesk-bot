"""
Web server for Telegram Mini App.

Provides endpoints for:
- Student ticket view (Mini App)
- Admin panel (future)
"""
import logging
from aiohttp import web
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from database.setup import new_session
from database.models import Ticket, User, TicketStatus, SourceType
from core.config import settings

logger = logging.getLogger(__name__)


async def index(request: web.Request) -> web.Response:
    """Main page redirect to student tickets view."""
    raise web.HTTPFound('/webapp/tickets')


async def health(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok"})


async def student_tickets(request: web.Request) -> web.Response:
    """
    Student ticket view page.
    
    This page is designed to be opened as a Telegram Mini App.
    It displays the student's tickets based on their Telegram user data
    passed via Telegram WebApp.initData.
    """
    return web.Response(
        text=STUDENT_TICKETS_HTML,
        content_type='text/html'
    )


async def api_tickets(request: web.Request) -> web.Response:
    """
    API endpoint to get tickets for a user.
    
    Query params:
        user_id: Telegram user ID (from WebApp init data)
    
    Returns:
        JSON list of tickets
    """
    user_id = request.query.get('user_id')
    
    if not user_id:
        return web.json_response(
            {"error": "user_id is required"},
            status=400
        )
    
    try:
        user_id = int(user_id)
    except ValueError:
        return web.json_response(
            {"error": "user_id must be a number"},
            status=400
        )
    
    async with new_session() as session:
        # Find the user
        stmt = select(User).where(
            User.external_id == user_id,
            User.source == SourceType.TELEGRAM
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return web.json_response({"tickets": []})
        
        # Get user's tickets
        stmt = (
            select(Ticket)
            .options(selectinload(Ticket.category))
            .where(Ticket.user_id == user.id)
            .order_by(desc(Ticket.created_at))
            .limit(20)
        )
        result = await session.execute(stmt)
        tickets = result.scalars().all()
        
        tickets_data = []
        for ticket in tickets:
            tickets_data.append({
                "id": ticket.id,
                "daily_id": ticket.daily_id,
                "status": ticket.status.value,
                "priority": ticket.priority.value,
                "category": ticket.category.name if ticket.category else None,
                "question_text": ticket.question_text[:200] if ticket.question_text else None,
                "summary": ticket.summary,
                "rating": ticket.rating,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
            })
        
        return web.json_response({"tickets": tickets_data})


async def api_ticket_detail(request: web.Request) -> web.Response:
    """
    API endpoint to get ticket details.
    
    Path params:
        ticket_id: Ticket ID
    Query params:
        user_id: Telegram user ID (for ownership verification)
    """
    ticket_id = request.match_info.get('ticket_id')
    user_id = request.query.get('user_id')
    
    if not user_id:
        return web.json_response(
            {"error": "user_id is required"},
            status=400
        )
    
    try:
        ticket_id = int(ticket_id)
        user_id = int(user_id)
    except ValueError:
        return web.json_response(
            {"error": "Invalid ID format"},
            status=400
        )
    
    async with new_session() as session:
        # Find the user
        stmt = select(User).where(
            User.external_id == user_id,
            User.source == SourceType.TELEGRAM
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return web.json_response(
                {"error": "User not found"},
                status=404
            )
        
        # Get the ticket
        stmt = (
            select(Ticket)
            .options(
                selectinload(Ticket.category),
                selectinload(Ticket.messages)
            )
            .where(Ticket.id == ticket_id)
        )
        result = await session.execute(stmt)
        ticket = result.scalar_one_or_none()
        
        if not ticket:
            return web.json_response(
                {"error": "Ticket not found"},
                status=404
            )
        
        # Verify ownership
        if ticket.user_id != user.id:
            return web.json_response(
                {"error": "Access denied"},
                status=403
            )
        
        # Build response
        messages = []
        for msg in sorted(ticket.messages, key=lambda m: m.created_at):
            messages.append({
                "id": msg.id,
                "sender_role": msg.sender_role.value,
                "text": msg.text,
                "content_type": msg.content_type,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })
        
        ticket_data = {
            "id": ticket.id,
            "daily_id": ticket.daily_id,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "category": ticket.category.name if ticket.category else None,
            "question_text": ticket.question_text,
            "summary": ticket.summary,
            "rating": ticket.rating,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
            "messages": messages,
        }
        
        return web.json_response({"ticket": ticket_data})


def create_app() -> web.Application:
    """Create and configure the aiohttp web application."""
    app = web.Application()
    
    # Add routes
    app.router.add_get('/', index)
    app.router.add_get('/health', health)
    app.router.add_get('/webapp/tickets', student_tickets)
    app.router.add_get('/api/tickets', api_tickets)
    app.router.add_get('/api/tickets/{ticket_id}', api_ticket_detail)
    
    return app


async def start_webapp() -> web.AppRunner:
    """Start the web application server."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(
        runner,
        settings.WEBAPP_HOST,
        settings.WEBAPP_PORT
    )
    await site.start()
    
    logger.info(f"Mini App web server started on {settings.WEBAPP_HOST}:{settings.WEBAPP_PORT}")
    return runner


# HTML template for student tickets view
STUDENT_TICKETS_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Мои заявки</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --tg-theme-bg-color: #ffffff;
            --tg-theme-text-color: #000000;
            --tg-theme-hint-color: #999999;
            --tg-theme-link-color: #2481cc;
            --tg-theme-button-color: #2481cc;
            --tg-theme-button-text-color: #ffffff;
            --tg-theme-secondary-bg-color: #f4f4f5;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--tg-theme-bg-color);
            color: var(--tg-theme-text-color);
            padding: 16px;
            min-height: 100vh;
        }
        
        h1 {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 16px;
            text-align: center;
        }
        
        .ticket-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .ticket-card {
            background: var(--tg-theme-secondary-bg-color);
            border-radius: 12px;
            padding: 16px;
            cursor: pointer;
            transition: transform 0.15s ease;
        }
        
        .ticket-card:active {
            transform: scale(0.98);
        }
        
        .ticket-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .ticket-id {
            font-weight: 600;
            font-size: 16px;
        }
        
        .ticket-status {
            font-size: 12px;
            padding: 4px 8px;
            border-radius: 8px;
            font-weight: 500;
        }
        
        .status-new {
            background: #fef3c7;
            color: #92400e;
        }
        
        .status-in_progress {
            background: #dbeafe;
            color: #1e40af;
        }
        
        .status-closed {
            background: #d1fae5;
            color: #065f46;
        }
        
        .ticket-category {
            font-size: 14px;
            color: var(--tg-theme-hint-color);
            margin-bottom: 8px;
        }
        
        .ticket-text {
            font-size: 14px;
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        
        .ticket-date {
            font-size: 12px;
            color: var(--tg-theme-hint-color);
            margin-top: 8px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--tg-theme-hint-color);
        }
        
        .empty {
            text-align: center;
            padding: 40px;
            color: var(--tg-theme-hint-color);
        }
        
        .error {
            text-align: center;
            padding: 20px;
            color: #dc2626;
            background: #fef2f2;
            border-radius: 8px;
        }
        
        /* Ticket detail view */
        .ticket-detail {
            display: none;
        }
        
        .ticket-detail.active {
            display: block;
        }
        
        .back-button {
            background: none;
            border: none;
            color: var(--tg-theme-link-color);
            font-size: 16px;
            cursor: pointer;
            padding: 8px 0;
            margin-bottom: 16px;
        }
        
        .detail-header {
            margin-bottom: 16px;
        }
        
        .detail-status {
            display: inline-block;
            margin-left: 8px;
        }
        
        .messages-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-top: 16px;
        }
        
        .message {
            padding: 12px;
            border-radius: 12px;
            max-width: 85%;
        }
        
        .message-user {
            background: var(--tg-theme-button-color);
            color: var(--tg-theme-button-text-color);
            align-self: flex-end;
            margin-left: auto;
        }
        
        .message-admin {
            background: var(--tg-theme-secondary-bg-color);
            align-self: flex-start;
        }
        
        .message-text {
            font-size: 14px;
            line-height: 1.4;
        }
        
        .message-time {
            font-size: 11px;
            opacity: 0.7;
            margin-top: 4px;
        }
        
        .rating-stars {
            font-size: 20px;
            margin-top: 16px;
            text-align: center;
        }
        
        .summary-block {
            background: var(--tg-theme-secondary-bg-color);
            padding: 12px;
            border-radius: 8px;
            margin-top: 16px;
        }
        
        .summary-title {
            font-weight: 600;
            margin-bottom: 8px;
        }
    </style>
</head>
<body>
    <div id="list-view">
        <h1>📂 Мои заявки</h1>
        <div id="tickets-container" class="loading">
            Загрузка...
        </div>
    </div>
    
    <div id="detail-view" class="ticket-detail">
        <button class="back-button" onclick="showList()">← Назад</button>
        <div id="ticket-detail-content"></div>
    </div>
    
    <script>
        // Initialize Telegram WebApp
        const tg = window.Telegram?.WebApp;
        let userId = null;
        
        if (tg) {
            tg.ready();
            tg.expand();
            
            // Apply Telegram theme
            document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color || '#ffffff');
            document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color || '#000000');
            document.documentElement.style.setProperty('--tg-theme-hint-color', tg.themeParams.hint_color || '#999999');
            document.documentElement.style.setProperty('--tg-theme-link-color', tg.themeParams.link_color || '#2481cc');
            document.documentElement.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color || '#2481cc');
            document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.themeParams.button_text_color || '#ffffff');
            document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams.secondary_bg_color || '#f4f4f5');
            
            // Get user ID from init data
            if (tg.initDataUnsafe?.user?.id) {
                userId = tg.initDataUnsafe.user.id;
            }
        }
        
        // Status translations
        const statusLabels = {
            'new': 'Новая',
            'in_progress': 'В работе',
            'closed': 'Закрыта'
        };
        
        // Format date
        function formatDate(isoString) {
            if (!isoString) return '';
            const date = new Date(isoString);
            return date.toLocaleDateString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        }
        
        // Load tickets
        async function loadTickets() {
            const container = document.getElementById('tickets-container');
            
            if (!userId) {
                container.innerHTML = '<div class="error">Ошибка: не удалось получить данные пользователя</div>';
                return;
            }
            
            try {
                const response = await fetch(`/api/tickets?user_id=${userId}`);
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Ошибка загрузки');
                }
                
                if (data.tickets.length === 0) {
                    container.innerHTML = '<div class="empty">У вас пока нет заявок</div>';
                    return;
                }
                
                container.className = 'ticket-list';
                container.innerHTML = data.tickets.map(ticket => `
                    <div class="ticket-card" onclick="showTicket(${ticket.id})">
                        <div class="ticket-header">
                            <span class="ticket-id">Заявка #${ticket.daily_id}</span>
                            <span class="ticket-status status-${ticket.status}">${statusLabels[ticket.status] || ticket.status}</span>
                        </div>
                        ${ticket.category ? `<div class="ticket-category">📁 ${escapeHtml(ticket.category)}</div>` : ''}
                        <div class="ticket-text">${escapeHtml(ticket.question_text || '')}</div>
                        <div class="ticket-date">${formatDate(ticket.created_at)}</div>
                    </div>
                `).join('');
                
            } catch (error) {
                container.innerHTML = `<div class="error">Ошибка: ${escapeHtml(error.message)}</div>`;
            }
        }
        
        // Show ticket detail
        async function showTicket(ticketId) {
            document.getElementById('list-view').style.display = 'none';
            document.getElementById('detail-view').classList.add('active');
            
            const content = document.getElementById('ticket-detail-content');
            content.innerHTML = '<div class="loading">Загрузка...</div>';
            
            try {
                const response = await fetch(`/api/tickets/${ticketId}?user_id=${userId}`);
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Ошибка загрузки');
                }
                
                const ticket = data.ticket;
                
                let html = `
                    <div class="detail-header">
                        <h1>Заявка #${ticket.daily_id}
                            <span class="ticket-status detail-status status-${ticket.status}">${statusLabels[ticket.status] || ticket.status}</span>
                        </h1>
                        ${ticket.category ? `<div class="ticket-category">📁 ${escapeHtml(ticket.category)}</div>` : ''}
                        <div class="ticket-date">Создана: ${formatDate(ticket.created_at)}</div>
                        ${ticket.closed_at ? `<div class="ticket-date">Закрыта: ${formatDate(ticket.closed_at)}</div>` : ''}
                    </div>
                `;
                
                // Messages
                if (ticket.messages && ticket.messages.length > 0) {
                    html += '<div class="messages-list">';
                    ticket.messages.forEach(msg => {
                        const isUser = msg.sender_role === 'user';
                        html += `
                            <div class="message ${isUser ? 'message-user' : 'message-admin'}">
                                <div class="message-text">${escapeHtml(msg.text || '')}</div>
                                <div class="message-time">${formatDate(msg.created_at)}</div>
                            </div>
                        `;
                    });
                    html += '</div>';
                }
                
                // Summary
                if (ticket.summary) {
                    html += `
                        <div class="summary-block">
                            <div class="summary-title">📋 Итог:</div>
                            <div>${escapeHtml(ticket.summary)}</div>
                        </div>
                    `;
                }
                
                // Rating
                if (ticket.rating) {
                    html += `<div class="rating-stars">${'⭐'.repeat(ticket.rating)}</div>`;
                }
                
                content.innerHTML = html;
                
            } catch (error) {
                content.innerHTML = `<div class="error">Ошибка: ${escapeHtml(error.message)}</div>`;
            }
        }
        
        // Show list view
        function showList() {
            document.getElementById('list-view').style.display = 'block';
            document.getElementById('detail-view').classList.remove('active');
        }
        
        // Escape HTML to prevent XSS
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Load tickets on page load
        loadTickets();
    </script>
</body>
</html>
"""
