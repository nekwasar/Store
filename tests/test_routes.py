import os
import pytest
from httpx import Client

BASE = os.environ.get("TEST_BASE_URL", "http://82.24.19.118:8989")


@pytest.fixture(scope="module")
def client():
    with Client(base_url=BASE, timeout=10) as c:
        yield c


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_root_redirects(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303


def test_product_list(client):
    response = client.get("/product/")
    assert response.status_code == 200


def test_category_api(client):
    response = client.get("/category/")
    assert response.status_code == 200


def test_cart_empty_redirects(client):
    response = client.get("/cart/", follow_redirects=False)
    assert response.status_code == 303


def test_order_page(client):
    response = client.get("/order/")
    assert response.status_code == 200


def test_login_page(client):
    response = client.get("/user/login")
    assert response.status_code == 200


def test_login_invalid(client):
    response = client.post("/user/login", data={
        "username": "no_user_xyz",
        "password": "wrong",
    })
    assert response.status_code == 200


def test_register_page(client):
    response = client.get("/user/register")
    assert response.status_code == 200


def test_setup_page(client):
    response = client.get("/user/setup")
    assert response.status_code == 200


def test_metrics(client):
    response = client.get("/metrics")
    assert response.status_code == 200


def test_admin_redirects(client):
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code == 307


def test_payment_canceled(client):
    response = client.get("/payment/canceled")
    assert response.status_code == 200


def test_product_search(client):
    response = client.get("/product/search?q=test")
    assert response.status_code == 200


def test_not_found(client):
    response = client.get("/nonexistent")
    assert response.status_code == 404


def test_security_headers(client):
    response = client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
