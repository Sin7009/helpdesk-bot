"""
Web server for Telegram Mini App.

Provides endpoints for:
- Student ticket view (Mini App)
- Admin panel
"""
import logging
from aiohttp import web
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload

from database.setup import new_session
from database.models import Ticket, User, TicketStatus, SourceType, UserRole
from core.config import settings

logger = logging.getLogger(__name__)


# --- Handlers ---

async def index(request: web.Request) -> web.Response:
    """Main page redirect to student tickets view."""
    raise web.HTTPFound('/webapp/tickets')


async def health(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok"})


async def student_tickets(request: web.Request) -> web.Response:
    """Student ticket view page (Mini App)."""
    return web.Response(text=STUDENT_TICKETS_HTML, content_type='text/html')


async def admin_dashboard(request: web.Request) -> web.Response:
    """Admin dashboard view page."""
    return web.Response(text=ADMIN_PANEL_HTML, content_type='text/html')


async def api_tickets(request: web.Request) -> web.Response:
    """
    Get tickets for a specific user (Student View).
    """
    user_id = request.query.get('user_id')
    
    if not user_id:
        return web.json_response({"error": "user_id is required"}, status=400)
    
    try:
        user_id = int(user_id)
    except ValueError:
        return web.json_response({"error": "user_id must be a number"}, status=400)
    
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
        
        return web.json_response({"tickets": [format_ticket(t) for t in tickets]})


async def api_ticket_detail(request: web.Request) -> web.Response:
    """
    Get detailed ticket info.
    """
    ticket_id = request.match_info.get('ticket_id')
    user_id = request.query.get('user_id')
    
    if not user_id:
        return web.json_response({"error": "user_id is required"}, status=400)
    
    try:
        ticket_id = int(ticket_id)
        user_id = int(user_id)
    except ValueError:
        return web.json_response({"error": "Invalid ID format"}, status=400)
    
    async with new_session() as session:
        # Find user
        stmt = select(User).where(
            User.external_id == user_id,
            User.source == SourceType.TELEGRAM
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return web.json_response({"error": "User not found"}, status=404)
        
        # Get ticket
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
            return web.json_response({"error": "Ticket not found"}, status=404)
        
        # Verify ownership or admin rights
        is_admin = user.role in [UserRole.ADMIN, UserRole.MODERATOR]
        if ticket.user_id != user.id and not is_admin:
            return web.json_response({"error": "Access denied"}, status=403)
        
        # Build response
        ticket_data = format_ticket(ticket)
        
        messages = []
        for msg in sorted(ticket.messages, key=lambda m: m.created_at):
            messages.append({
                "id": msg.id,
                # ИСПРАВЛЕНИЕ: Проверяем, есть ли атрибут value, или используем как строку
                "sender_role": msg.sender_role.value if hasattr(msg.sender_role, 'value') else msg.sender_role,
                "text": msg.text,
                "content_type": msg.content_type,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })
        ticket_data["messages"] = messages
        
        return web.json_response({"ticket": ticket_data})


async def api_admin_data(request: web.Request) -> web.Response:
    """
    Get stats and recent tickets (Admin View).
    """
    user_id = request.query.get('user_id')
    if not user_id:
        return web.json_response({"error": "Auth required"}, status=401)

    try:
        user_id = int(user_id)
    except ValueError:
        return web.json_response({"error": "Invalid user_id"}, status=400)

    async with new_session() as session:
        # 1. Check Admin Rights
        stmt = select(User).where(User.external_id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        if not user or user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return web.json_response({"error": "Access denied"}, status=403)

        # 2. Optimized Statistics (GROUP BY)
        stats_stmt = select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
        stats_result = (await session.execute(stats_stmt)).all()
        
        raw_stats = {row[0]: row[1] for row in stats_result}
        
        # Fill missing statuses with 0
        stats = {
            status.value: raw_stats.get(status, 0)
            for status in TicketStatus
        }

        # 3. Load recent tickets
        tickets_stmt = (
            select(Ticket)
            .options(selectinload(Ticket.user), selectinload(Ticket.category))
            .order_by(desc(Ticket.created_at))
            .limit(50)
        )
        tickets = (await session.execute(tickets_stmt)).scalars().all()

        tickets_data = []
        for t in tickets:
            user_name = t.user.full_name or t.user.username or f"ID {t.user.external_id}"
            tickets_data.append({
                "id": t.id,
                "daily_id": t.daily_id,
                # ИСПРАВЛЕНИЕ: Безопасное получение значения Enum
                "status": t.status.value if hasattr(t.status, 'value') else t.status,
                "priority": t.priority.value if hasattr(t.priority, 'value') else t.priority,
                "user_name": user_name,
                "category": t.category.name if t.category else "—",
                "question_short": (t.question_text[:60] + '...') if t.question_text else '',
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })

        return web.json_response({
            "stats": stats,
            "tickets": tickets_data
        })


# --- Helpers ---

def format_ticket(ticket: Ticket) -> dict:
    return {
        "id": ticket.id,
        "daily_id": ticket.daily_id,
        # ИСПРАВЛЕНИЕ: Проверяем наличие атрибута value
        "status": ticket.status.value if hasattr(ticket.status, 'value') else ticket.status,
        "priority": ticket.priority.value if hasattr(ticket.priority, 'value') else ticket.priority,
        "category": ticket.category.name if ticket.category else None,
        "question_text": ticket.question_text[:200] if ticket.question_text else None,
        "summary": ticket.summary,
        "rating": ticket.rating,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
    }


def create_app() -> web.Application:
    """Create and configure the aiohttp web application."""
    app = web.Application()
    
    # Add routes
    app.router.add_get('/', index)
    app.router.add_get('/health', health)
    app.router.add_get('/webapp/tickets', student_tickets)
    app.router.add_get('/webapp/admin', admin_dashboard)  # Admin route
    app.router.add_get('/api/tickets', api_tickets)
    app.router.add_get('/api/tickets/{ticket_id}', api_ticket_detail)
    app.router.add_get('/api/admin/data', api_admin_data) # Admin API
    
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


# --- Templates ---

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
        body { font-family: -apple-system, sans-serif; background: var(--tg-theme-bg-color); color: var(--tg-theme-text-color); padding: 16px; margin:0;}
        .card { background: var(--tg-theme-secondary-bg-color); border-radius: 12px; padding: 16px; margin-bottom: 12px; cursor: pointer; }
        .header { display: flex; justify-content: space-between; margin-bottom: 8px; font-weight: 600; }
        .status { padding: 4px 8px; border-radius: 6px; font-size: 12px; }
        .status-new { background: #fee2e2; color: #991b1b; }
        .status-in_progress { background: #dbeafe; color: #1e40af; }
        .status-closed { background: #d1fae5; color: #065f46; }
        .date { font-size: 12px; color: var(--tg-theme-hint-color); margin-top: 8px; }
        /* Detail view */
        #detail { display: none; }
        .msg { padding: 10px; margin: 8px 0; border-radius: 10px; max-width: 85%; }
        .msg-user { background: var(--tg-theme-button-color); color: var(--tg-theme-button-text-color); margin-left: auto; }
        .msg-admin { background: var(--tg-theme-secondary-bg-color); }
    </style>
</head>
<body>
    <div id="list">
        <h2 style="text-align:center; margin-bottom:20px;">📂 Мои обращения</h2>
        <div id="container">Загрузка...</div>
    </div>
    <div id="detail">
        <button onclick="goBack()" style="background:none;border:none;color:var(--tg-theme-link-color);padding:10px 0;font-size:16px;">← Назад</button>
        <div id="detail-content"></div>
    </div>
    <script>
        const tg = window.Telegram?.WebApp;
        if(tg) { tg.ready(); tg.expand(); }
        const userId = tg?.initDataUnsafe?.user?.id;
        const statusMap = {'new': 'Новая', 'in_progress': 'В работе', 'closed': 'Закрыта'};

        async function load() {
            if(!userId) return document.getElementById('container').innerHTML = 'Ошибка auth';
            try {
                const res = await fetch(`/api/tickets?user_id=${userId}`);
                const data = await res.json();
                const html = data.tickets.length ? data.tickets.map(t => `
                    <div class="card" onclick="openTicket(${t.id})">
                        <div class="header">
                            <span>#${t.daily_id}</span>
                            <span class="status status-${t.status}">${statusMap[t.status] || t.status}</span>
                        </div>
                        <div style="font-size:14px; margin-bottom:4px; opacity:0.7">${t.category || ''}</div>
                        <div>${escapeHtml(t.question_text || '')}</div>
                        <div class="date">${new Date(t.created_at).toLocaleDateString()}</div>
                    </div>
                `).join('') : '<div style="text-align:center;color:gray;margin-top:50px;">Заявок нет</div>';
                document.getElementById('container').innerHTML = html;
            } catch(e) { document.getElementById('container').innerHTML = 'Ошибка сети'; }
        }

        async function openTicket(id) {
            document.getElementById('list').style.display='none';
            document.getElementById('detail').style.display='block';
            document.getElementById('detail-content').innerHTML = 'Загрузка...';
            
            const res = await fetch(`/api/tickets/${id}?user_id=${userId}`);
            const data = await res.json();
            const t = data.ticket;
            
            let html = `<h2>Заявка #${t.daily_id}</h2>
                <div style="margin-bottom:20px; color:gray">${t.category || 'Без категории'}</div>`;
            
            if(t.messages) {
                html += t.messages.map(m => `
                    <div class="msg ${m.sender_role === 'user' ? 'msg-user' : 'msg-admin'}">
                        <div>${escapeHtml(m.text || '[Вложение]')}</div>
                        <div style="font-size:10px; opacity:0.7; margin-top:4px; text-align:right">
                            ${new Date(m.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                        </div>
                    </div>
                `).join('');
            }
            document.getElementById('detail-content').innerHTML = html;
        }

        function goBack() {
            document.getElementById('detail').style.display='none';
            document.getElementById('list').style.display='block';
        }
        
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        load();
    </script>
</body>
</html>"""

ADMIN_PANEL_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Админ-панель</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #f5f5f5; --card: #fff; --text: #000; --accent: #2481cc; }
        body { font-family: -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 12px; margin:0; }
        
        .stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 20px; }
        .stat-card { background: var(--card); padding: 12px; border-radius: 10px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .stat-num { font-size: 20px; font-weight: 700; display: block; }
        .stat-lbl { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; display: block;}
        
        h3 { margin: 0 0 10px 4px; font-size: 16px; opacity: 0.8; }
        
        .row { background: var(--card); padding: 12px; border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .row-left { flex: 1; min-width: 0; padding-right: 10px; }
        .row-user { font-weight: 600; font-size: 14px; color: var(--accent); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .row-txt { font-size: 13px; color: #333; margin: 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .row-meta { font-size: 11px; color: #999; }
        
        .badge { font-size: 10px; padding: 4px 8px; border-radius: 12px; font-weight: 600; white-space: nowrap; }
        .st-new { background: #fee2e2; color: #ef4444; }
        .st-in_progress { background: #dbeafe; color: #3b82f6; }
        .st-closed { background: #f3f4f6; color: #6b7280; }
    </style>
</head>
<body>
    <div id="stats" class="stat-grid">Loading...</div>
    <h3>Последние заявки</h3>
    <div id="tickets"></div>

    <script>
        const tg = window.Telegram?.WebApp;
        if(tg) { tg.ready(); tg.expand(); }
        const userId = tg?.initDataUnsafe?.user?.id;
        const statusLabels = {'new': 'Новая', 'in_progress': 'В работе', 'closed': 'Закрыта'};

        async function init() {
            if(!userId) return document.body.innerHTML = 'Error: No User ID';
            try {
                const res = await fetch(`/api/admin/data?user_id=${userId}`);
                if(res.status === 403) return document.body.innerHTML = '<h2 style="color:red;text-align:center;margin-top:50px">Нет доступа</h2>';
                
                const data = await res.json();
                renderStats(data.stats);
                renderTickets(data.tickets);
            } catch(e) { document.body.innerHTML = 'Error: ' + e.message; }
        }

        function renderStats(s) {
            document.getElementById('stats').innerHTML = `
                <div class="stat-card">
                    <span class="stat-num" style="color:#ef4444">${s.new || 0}</span>
                    <span class="stat-lbl">Новые</span>
                </div>
                <div class="stat-card">
                    <span class="stat-num" style="color:#3b82f6">${s.in_progress || 0}</span>
                    <span class="stat-lbl">В работе</span>
                </div>
                <div class="stat-card">
                    <span class="stat-num" style="color:#6b7280">${s.closed || 0}</span>
                    <span class="stat-lbl">Закрыто</span>
                </div>
            `;
        }

        function renderTickets(list) {
            document.getElementById('tickets').innerHTML = list.map(t => `
                <div class="row">
                    <div class="row-left">
                        <div class="row-user">#${t.daily_id} • ${escapeHtml(t.user_name)}</div>
                        <div class="row-txt">${escapeHtml(t.question_short || 'Без текста')}</div>
                        <div class="row-meta">${t.category} • ${new Date(t.created_at).toLocaleDateString()}</div>
                    </div>
                    <div class="badge st-${t.status}">${statusLabels[t.status] || t.status}</div>
                </div>
            `).join('');
        }
        
        function escapeHtml(s) {
            return s ? s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : '';
        }

        init();
    </script>
</body>
</html>"""
