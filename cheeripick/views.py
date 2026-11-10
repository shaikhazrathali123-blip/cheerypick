from django.shortcuts import redirect, render


def landing(request):
    if request.user.is_authenticated:
        return redirect("matching:deck")
    return render(request, "landing.html")


def page_not_found(request, exception=None):
    return render(request, "404.html", status=404)


def preview_404(request):
    return page_not_found(request)
