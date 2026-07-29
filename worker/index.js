/* Sites 静态站入口：将请求交给构建产物中的静态资源绑定。 */
export default {
  async fetch(request, env) {
    var response = await env.ASSETS.fetch(request);
    if (response.status !== 404) return response;

    var url = new URL(request.url);
    if (url.pathname.endsWith('/')) {
      url.pathname += 'index.html';
    } else if (!url.pathname.split('/').pop().includes('.')) {
      url.pathname += '.html';
    } else {
      return response;
    }
    return env.ASSETS.fetch(new Request(url, request));
  }
};
