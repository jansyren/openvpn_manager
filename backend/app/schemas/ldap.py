from typing import Literal

from pydantic import BaseModel, Field


class LdapConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    server_url: str = Field(..., min_length=1, max_length=256)
    server_url_backup: str | None = None
    bind_dn: str = Field(..., min_length=1, max_length=512)
    bind_password: str = Field(..., min_length=1, max_length=256)
    user_search_base: str = Field(..., min_length=1, max_length=512)
    user_filter: str = Field("(objectClass=user)", max_length=256)
    username_attr: str = Field("sAMAccountName", max_length=64)
    group_search_base: str | None = None
    group_member_attr: str = Field("member", max_length=64)
    use_tls: bool = True
    tls_verify_cert: bool = False
    ca_cert_pem: str | None = None
    is_active: bool = True


class LdapConfigUpdate(BaseModel):
    name: str | None = None
    server_url: str | None = None
    server_url_backup: str | None = None
    bind_dn: str | None = None
    bind_password: str | None = None
    user_search_base: str | None = None
    user_filter: str | None = None
    username_attr: str | None = None
    group_search_base: str | None = None
    group_member_attr: str | None = None
    use_tls: bool | None = None
    tls_verify_cert: bool | None = None
    ca_cert_pem: str | None = None
    is_active: bool | None = None


class LdapConfigRead(BaseModel):
    id: int
    name: str
    server_url: str
    server_url_backup: str | None
    bind_dn: str
    user_search_base: str
    user_filter: str
    username_attr: str
    group_search_base: str | None
    group_member_attr: str
    use_tls: bool
    tls_verify_cert: bool
    ca_cert_pem: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class LdapGroupRoleMappingCreate(BaseModel):
    group_dn: str = Field(..., min_length=1, max_length=512)
    role: Literal["admin", "operator", "viewer", "vpn_user"]


class LdapGroupRoleMappingRead(BaseModel):
    id: int
    ldap_config_id: int
    group_dn: str
    role: str

    model_config = {"from_attributes": True}


class VpnInstanceLdapGroupCreate(BaseModel):
    ldap_config_id: int
    group_dn: str = Field(..., min_length=1, max_length=512)
    display_name: str | None = Field(None, max_length=128)


class VpnInstanceLdapGroupRead(BaseModel):
    id: int
    vpn_instance_id: int
    ldap_config_id: int
    group_dn: str
    display_name: str | None

    model_config = {"from_attributes": True}


class LdapTestResult(BaseModel):
    success: bool
    message: str


class LdapSyncResult(BaseModel):
    users_created: int
    clients_created: int
    certs_issued: int
    skipped: int
    failed: list[str]
