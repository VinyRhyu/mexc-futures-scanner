## Experimento paralelo: rompimento a favor da estrutura de 1h

Atualização: 2026-11-10T18:01:42+00:00.
Coleta prospectiva: 2026-11-10T13:30:00+00:00 até 2026-11-24T13:30:00+00:00.

LONG somente em ALTA; SHORT somente em BAIXA. INDEFINIDA/DESCONHECIDA são excluídas.
ANTECIPADA e CONFIRMADA são simulações independentes, não carteiras somáveis.

| Amostra com 4h completas | Tipo | Candidatos | Regra | Entradas | Alvos | Stops | Abertas | R encerradas |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| RESERVADA_PRELIMINAR | ANTECIPADA | 8 | ATUAL | 0 | 0 | 0 | 0 | 0.000 |
| RESERVADA_PRELIMINAR | ANTECIPADA | 8 | FILTRO_1H | 0 | 0 | 0 | 0 | 0.000 |
| RESERVADA_PRELIMINAR | CONFIRMADA | 6 | ATUAL | 0 | 0 | 0 | 0 | 0.000 |
| RESERVADA_PRELIMINAR | CONFIRMADA | 6 | FILTRO_1H | 0 | 0 | 0 | 0 | 0.000 |
| PROSPECTIVA | ANTECIPADA | 6 | ATUAL | 0 | 0 | 0 | 0 | 0.000 |
| PROSPECTIVA | ANTECIPADA | 6 | FILTRO_1H | 0 | 0 | 0 | 0 | 0.000 |
| PROSPECTIVA | CONFIRMADA | 6 | ATUAL | 0 | 0 | 0 | 0 | 0.000 |
| PROSPECTIVA | CONFIRMADA | 6 | FILTRO_1H | 0 | 0 | 0 | 0 | 0.000 |

### Como interpretar

- O filtro só remove sinais. Contamos stops evitados e alvos bons descartados.
- Amostra reservada começa após 10/11/2026 10:58:54 UTC; não foi usada nos ajustes anteriores.
- Prospectiva começa após registrar este protocolo. Capturas tardias ficam separadas da comparação principal.
- Novas posições precisam de até 4h para a janela completa; abertas não são vitórias.
- Entrada na abertura seguinte, taxa 0,06% por lado, spread 0,02%, slippage configurado ou dois ticks, funding zero e livro infinito hipotéticos.
- Usa regras do contrato congeladas na primeira captura; sem latência real e sem execução de ordens.
- Soma R compara sinais independentes e sobrepostos, não o saldo de uma carteira de 1 USDT.
- Nenhum alerta do bot é filtrado por este experimento. Mudanças no calculador/configuração pausam a coleta para evitar misturar regras.
- 14 dias não garantem amostra suficiente; resultados permanecem exploratórios.

```json
{
  "RESERVADA_PRELIMINAR": {
    "ANTECIPADA": {
      "all": {
        "candidates": 8,
        "structure_counts": {
          "INDEFINIDA": 5,
          "BAIXA": 2,
          "ALTA": 1
        },
        "capture_late": 8,
        "models": {
          "ATUAL": {
            "candidates": 8,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 8
            }
          },
          "FILTRO_1H": {
            "candidates": 0,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {}
          }
        },
        "removed_winners": 0,
        "avoided_stops": 0
      },
      "complete": {
        "candidates": 8,
        "structure_counts": {
          "INDEFINIDA": 5,
          "BAIXA": 2,
          "ALTA": 1
        },
        "capture_late": 8,
        "models": {
          "ATUAL": {
            "candidates": 8,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 8
            }
          },
          "FILTRO_1H": {
            "candidates": 0,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {}
          }
        },
        "removed_winners": 0,
        "avoided_stops": 0
      },
      "timely_complete": {
        "candidates": 0,
        "structure_counts": {},
        "capture_late": 0,
        "models": {
          "ATUAL": {
            "candidates": 0,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {}
          },
          "FILTRO_1H": {
            "candidates": 0,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {}
          }
        },
        "removed_winners": 0,
        "avoided_stops": 0
      }
    },
    "CONFIRMADA": {
      "all": {
        "candidates": 6,
        "structure_counts": {
          "INDEFINIDA": 4,
          "BAIXA": 2
        },
        "capture_late": 6,
        "models": {
          "ATUAL": {
            "candidates": 6,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 6
            }
          },
          "FILTRO_1H": {
            "candidates": 1,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 1
            }
          }
        },
        "removed_winners": 0,
        "avoided_stops": 0
      },
      "complete": {
        "candidates": 6,
        "structure_counts": {
          "INDEFINIDA": 4,
          "BAIXA": 2
        },
        "capture_late": 6,
        "models": {
          "ATUAL": {
            "candidates": 6,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 6
            }
          },
          "FILTRO_1H": {
            "candidates": 1,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 1
            }
          }
        },
        "removed_winners": 0,
        "avoided_stops": 0
      },
      "timely_complete": {
        "candidates": 0,
        "structure_counts": {},
        "capture_late": 0,
        "models": {
          "ATUAL": {
            "candidates": 0,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {}
          },
          "FILTRO_1H": {
            "candidates": 0,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {}
          }
        },
        "removed_winners": 0,
        "avoided_stops": 0
      }
    }
  },
  "PROSPECTIVA": {
    "ANTECIPADA": {
      "all": {
        "candidates": 8,
        "structure_counts": {
          "BAIXA": 2,
          "ALTA": 1,
          "INDEFINIDA": 5
        },
        "capture_late": 0,
        "models": {
          "ATUAL": {
            "candidates": 8,
            "entries": 1,
            "targets": 0,
            "stops": 1,
            "open": 0,
            "closed_r_independent": "-1",
            "marked_r_independent": "-1",
            "outcomes": {
              "BLOQUEADA": 7,
              "STOP": 1
            }
          },
          "FILTRO_1H": {
            "candidates": 2,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 2
            }
          }
        },
        "removed_winners": 0,
        "avoided_stops": 1
      },
      "complete": {
        "candidates": 6,
        "structure_counts": {
          "BAIXA": 2,
          "ALTA": 1,
          "INDEFINIDA": 3
        },
        "capture_late": 0,
        "models": {
          "ATUAL": {
            "candidates": 6,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 6
            }
          },
          "FILTRO_1H": {
            "candidates": 2,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 2
            }
          }
        },
        "removed_winners": 0,
        "avoided_stops": 0
      },
      "timely_complete": {
        "candidates": 6,
        "structure_counts": {
          "BAIXA": 2,
          "ALTA": 1,
          "INDEFINIDA": 3
        },
        "capture_late": 0,
        "models": {
          "ATUAL": {
            "candidates": 6,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 6
            }
          },
          "FILTRO_1H": {
            "candidates": 2,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 2
            }
          }
        },
        "removed_winners": 0,
        "avoided_stops": 0
      }
    },
    "CONFIRMADA": {
      "all": {
        "candidates": 6,
        "structure_counts": {
          "BAIXA": 2,
          "INDEFINIDA": 3,
          "ALTA": 1
        },
        "capture_late": 0,
        "models": {
          "ATUAL": {
            "candidates": 6,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 6
            }
          },
          "FILTRO_1H": {
            "candidates": 2,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 2
            }
          }
        },
        "removed_winners": 0,
        "avoided_stops": 0
      },
      "complete": {
        "candidates": 6,
        "structure_counts": {
          "BAIXA": 2,
          "INDEFINIDA": 3,
          "ALTA": 1
        },
        "capture_late": 0,
        "models": {
          "ATUAL": {
            "candidates": 6,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 6
            }
          },
          "FILTRO_1H": {
            "candidates": 2,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 2
            }
          }
        },
        "removed_winners": 0,
        "avoided_stops": 0
      },
      "timely_complete": {
        "candidates": 6,
        "structure_counts": {
          "BAIXA": 2,
          "INDEFINIDA": 3,
          "ALTA": 1
        },
        "capture_late": 0,
        "models": {
          "ATUAL": {
            "candidates": 6,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 6
            }
          },
          "FILTRO_1H": {
            "candidates": 2,
            "entries": 0,
            "targets": 0,
            "stops": 0,
            "open": 0,
            "closed_r_independent": "0",
            "marked_r_independent": "0",
            "outcomes": {
              "BLOQUEADA": 2
            }
          }
        },
        "removed_winners": 0,
        "avoided_stops": 0
      }
    }
  }
}
```
