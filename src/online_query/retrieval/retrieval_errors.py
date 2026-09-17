"""Online Retrieval 的内部 Contract 异常。"""


class RetrievalContractError(RuntimeError):
    """检索结果或已发布资产不满足在线契约。"""


class RequiredCandidateUnavailableError(RetrievalContractError):
    """当前问题所需的业务候选资源不可用，属于可拒答而非技术故障。"""
