"""
MySQL/MariaDB backend wrapper that allows MariaDB 10.4 (the version bundled
with XAMPP) even though modern Django officially requires 10.5/10.6+.

BHIMS only uses basic SQL features supported by MariaDB 10.4, so the official
minimum-version gate is lowered here instead of forcing a XAMPP upgrade.
Ideally, upgrade XAMPP's MariaDB when convenient and remove this override.
"""
from django.db.backends.mysql import base as mysql_base
from django.db.backends.mysql import features as mysql_features


class DatabaseFeatures(mysql_features.DatabaseFeatures):
    minimum_database_version = (10, 4)
    # INSERT ... RETURNING exists only on MariaDB 10.5+; XAMPP ships 10.4.
    can_return_columns_from_insert = False


class DatabaseWrapper(mysql_base.DatabaseWrapper):
    features_class = DatabaseFeatures
