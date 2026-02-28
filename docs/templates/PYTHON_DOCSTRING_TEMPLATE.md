# Python Docstring e Comentários

Template e guia rápido para documentação de código Python no projeto.

## Template de docstring (Google Style)

```python
def minha_funcao(parametro: str, limite: int = 10) -> list[str]:
    """Descrição breve e objetiva da função.

    Descrição complementar do comportamento, incluindo regras de negócio
    importantes e pré-condições não óbvias.

    Args:
        parametro: Descrição clara do parâmetro.
        limite: Limite máximo de itens processados.

    Returns:
        Lista de resultados processados.

    Raises:
        ValueError: Quando `parametro` estiver vazio.
        RuntimeError: Quando houver falha externa não recuperável.

    Example:
        >>> minha_funcao("direito administrativo", limite=5)
        ["resultado 1", "resultado 2"]
    """
```

## Quando comentar

| Comentar | Evitar comentar |
|----------|------------------|
| Regra de negócio (o porquê) | O óbvio (o que o código já mostra) |
| Decisão técnica não trivial | Linha a linha |
| Contrato de integração | Detalhes irrelevantes de implementação |

