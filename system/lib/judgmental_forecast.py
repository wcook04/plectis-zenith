"""Unsupported legacy quantile mode cannot silently enter the generic core."""
import math
LEVELS={'q10':.1,'q50':.5,'q90':.9}
def rule_errors(payload):
    return ['INVALID_QUANTILES: generic core requires numeric observation forecasts'] if 'forecast_quantiles' in payload else []
def target_errors(payload,*args): return []
def locked_evidence(payload): return None
def verify_truth(*args): raise ValueError('Legacy quantile mode is unsupported')
def score_quantiles(row,realized):
    losses={key:max(p*(realized-row[key]),(p-1)*(realized-row[key])) for key,p in LEVELS.items()}
    return {'quantile_pinball_losses':losses,'mean_quantile_pinball_loss':math.fsum(losses.values())/3}
