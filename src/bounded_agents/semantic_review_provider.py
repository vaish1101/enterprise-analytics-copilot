"""Semantic Review-only native response and bounded input adapter."""
import hashlib
import json
from urllib.parse import urlsplit
from src.llm.base import ProviderMalformedOutputError


def get(value, key, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def canonical_text(response):
    """Never aggregate output_text, merge chunks or salvage a JSON prefix."""
    if get(response,'status')!='completed':
        raise ProviderMalformedOutputError('Incomplete Semantic Review response')
    output=get(response,'output')
    if not isinstance(output,(list,tuple)):
        raise ProviderMalformedOutputError('Native Semantic Review output items missing')
    messages=[]
    for item in output:
        if get(item,'type')=='reasoning':
            continue  # Separate auxiliary metadata is never final answer text.
        if get(item,'type')!='message':
            raise ProviderMalformedOutputError('Unexpected Semantic Review output item')
        messages.append(item)
    if len(messages)!=1:
        raise ProviderMalformedOutputError('Semantic Review requires one assistant message')
    message=messages[0]
    if (get(message,'role')!='assistant' or get(message,'status')!='completed'
        or get(message,'channel') not in (None,'final')):
        raise ProviderMalformedOutputError('Semantic Review message not completed final output')
    content=get(message,'content')
    if not isinstance(content,(list,tuple)) or len(content)!=1 or get(content[0],'type')!='output_text':
        raise ProviderMalformedOutputError('Semantic Review requires one text content block')
    text=get(content[0],'text')
    if not isinstance(text,str) or not text:
        raise ProviderMalformedOutputError('Empty Semantic Review text')
    return text


def compact_input(payload):
    """Remove redundancy, never crop or reinterpret canonical evidence."""
    from .repair_targets import version, VERSION, checked_options
    repair_options = checked_options(payload) if version(payload) == VERSION else None
    docs=[]
    for item in payload.get('documents',()):
        if item.get('shortened'):
            raise ValueError('Semantic Review requires complete canonical evidence')
        docs.append({k:item[k] for k in ('id','text','source_id','content_hash','authenticity') if k in item})
    by_id={d['id']:d for d in docs}
    components={x['claim_id']:x for x in payload.get('components',())}
    claims=[]
    for item in payload.get('claims',()):
        value={k:item[k] for k in ('claim_id','text','claim_type','evidence_ids','causal_policy') if k in item}
        component=components.get(item['claim_id'])
        if component:
            value['provenance']={k:component[k] for k in ('role','authenticity','source_quotation') if k in component}
        ids=value.get('evidence_ids',())
        if (component and component.get('source_quotation') and len(ids)==1
            and ids[0] in by_id and value.get('text')==by_id[ids[0]]['text']):
            value.pop('text')
            value['text_from_evidence_id']=ids[0]  # Complete text appears once.
        claims.append(value)
    result = {'question':payload.get('question'), 'operation':payload.get('operation'),
        'required_answer_components':payload.get('answer_requirements',{}).get('required_components',()),
        'boundary_is_not_direct_answer':payload.get('answer_requirements',{}).get('boundary_is_not_direct_answer',False),
        'completeness':{k:v for k,v in payload.get('completeness',{}).items()
            if k in ('complete','missing_components','eligible_documentary_evidence')},
        'claims':claims,'documents':docs,
        'numeric_claims_are_canonical':payload.get('numeric_claims_are_canonical',False),
        'canonical_numeric_claim_ids':[x['claim_id'] for x in payload.get('numeric_handles',())],
        'limitations':list(dict.fromkeys(payload.get('limitations',()))),
        'completion_candidate_evidence_ids':list(payload.get('completion_candidate_evidence_ids',()))}
    if repair_options is not None:
        result['semantic_review_contract_version'] = VERSION
        result['repair_options'] = repair_options
    return result


def capture_http(raw):
    """Credential-free actual HTTP bodies; no hidden reasoning/headers."""
    http=raw.http_response
    request=http.request
    url=urlsplit(str(request.url))
    authority=url.hostname or ''
    if ':' in authority:authority='['+authority+']'
    if url.port:authority+=':'+str(url.port)
    body=json.loads(request.content)
    response=http.json()
    # Preserve native final content and item boundaries. Do not save hidden
    # reasoning/encrypted state; it cannot contribute to canonical review text.
    items=response.get('output',[])
    filtered=[]
    for item in items:
        if item.get('type')=='reasoning':
            filtered.append({k:item[k] for k in ('type','id','status') if k in item})
        else:
            filtered.append(item)
    safe={k:response[k] for k in ('id','model','status','incomplete_details','usage','text','error') if k in response}
    safe['output']=filtered
    return {'request':{'method':request.method,'endpoint':url.scheme+'://'+authority+url.path,
                       'body':body,'body_sha256':hashlib.sha256(request.content).hexdigest()},
            'response':{'http_status':http.status_code,'body':safe,
                        'native_body_sha256':hashlib.sha256(http.content).hexdigest()}}


def native_diagnostic(response):
    """Item-aware diagnostics; no SDK convenience-property concatenation."""
    items=get(response,'output',())
    result=[];texts=[]
    for item in items or ():
        entry={k:get(item,k) for k in ('type','id','role','status','channel') if get(item,k) is not None}
        if get(item,'type')=='message':
            content=[]
            for block in get(item,'content',()) or ():
                d={'type':get(block,'type')}
                if get(block,'type')=='output_text':
                    text=get(block,'text','')
                    if isinstance(text,str):
                        d.update(text=text[:65536],text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                                 text_truncated=len(text)>65536)
                        texts.append(text)
                content.append(d)
            entry['content']=content
        result.append(entry)
    # Legacy wire_output remains a single-block diagnostic only, never a join.
    text=texts[0] if len(texts)==1 else ''
    return {'native_output_items':result,'native_text_block_count':len(texts),
        'wire_output':text[:65536],'wire_output_truncated':len(text)>65536,
        'wire_output_sha256':hashlib.sha256(text.encode()).hexdigest()}
