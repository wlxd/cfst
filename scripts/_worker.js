addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  try {
    // 只允许 POST 请求
    if (request.method !== 'POST') {
      return new Response('Method Not Allowed', { status: 405 })
    }

    // 解析请求数据
    const data = await request.json()
    
    // 验证 SECRET_TOKEN
    const serverSecret = typeof SECRET_TOKEN === 'undefined' ? '' : SECRET_TOKEN
    if (serverSecret && data.secret_token !== serverSecret) {
      return new Response('Forbidden: Invalid token', { status: 403 })
    }

    // 检查必要参数
    if (!data.bot_token || !data.chat_id || !data.message) {
      return new Response('Bad Request: Missing parameters', { status: 400 })
    }

    // 发送 Telegram 消息
    const tgUrl = `https://api.telegram.org/bot${data.bot_token}/sendMessage`
    const response = await fetch(tgUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: data.chat_id,
        text: data.message
      })
    })

    // 处理 Telegram 响应
    if (!response.ok) {
      const error = await response.text()
      return new Response(`Telegram API Error: ${error}`, { status: 500 })
    }

    return new Response('Message sent successfully', { status: 200 })
  } catch (error) {
    return new Response(`Server Error: ${error.message}`, { status: 500 })
  }
}
