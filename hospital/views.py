from urllib.parse import urlencode

from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .fhir_loader import (
    count_by_resource_type,
    fhir_root,
    get_patient_resource,
    list_bundle_files,
    load_bundle,
    resources_by_type,
)

ALLOWED_RESOURCE_TYPES = frozenset({
    'Patient',
    'AllergyIntolerance',
    'CarePlan',
    'CareTeam',
    'Claim',
    'Condition',
    'Coverage',
    'Device',
    'DiagnosticReport',
    'Encounter',
    'ExplanationOfBenefit',
    'Goal',
    'Immunization',
    'ImagingStudy',
    'Medication',
    'MedicationAdministration',
    'MedicationRequest',
    'Observation',
    'Organization',
    'Practitioner',
    'Procedure',
    'ServiceRequest',
    'DocumentReference',
})


def _json(data, status=200):
    return JsonResponse(data, json_dumps_params={'ensure_ascii': False}, status=status, safe=isinstance(data, dict))


def _paginate(items, limit, offset):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    return items[offset : offset + limit], len(items)


@require_GET
def home(request):
    files = list_bundle_files()
    root = fhir_root()
    return render(
        request,
        'hospital/index.html',
        {
            'patient_count': len(files),
            'fhir_dir': str(root),
            'fhir_dir_exists': root.is_dir(),
        },
    )


@require_GET
def api_root(request):
    base = request.build_absolute_uri('/').rstrip('/')
    endpoints = {
        'patients_list': f'{base}/api/patients/',
        'patient_detail': f'{base}/api/patients/{{id}}/',
        'patient_bundle': f'{base}/api/patients/{{id}}/bundle/',
        'patient_resources': f'{base}/api/patients/{{id}}/resources/{{ResourceType}}/',
        'patient_resource_types': f'{base}/api/patients/{{id}}/resource-types/',
    }
    return _json({
        'name': 'Healthcare Lab — API FHIR (Synthea)',
        'fhir_data_dir': str(fhir_root()),
        'patient_bundles': len(list_bundle_files()),
        'endpoints': endpoints,
        'allowed_resource_types': sorted(ALLOWED_RESOURCE_TYPES),
    })


@require_GET
def patient_list(request):
    limit = int(request.GET.get('limit', 50))
    offset = int(request.GET.get('offset', 0))
    rows = [{'id': uid, 'display': label} for uid, label, _ in list_bundle_files()]
    page, total = _paginate(rows, limit, offset)
    q = {}
    if offset + limit < total:
        q['offset'] = offset + limit
        q['limit'] = limit
        next_url = request.build_absolute_uri(request.path) + '?' + urlencode(q)
    else:
        next_url = None
    if offset > 0:
        q['offset'] = max(0, offset - limit)
        q['limit'] = limit
        prev_url = request.build_absolute_uri(request.path) + '?' + urlencode(q)
    else:
        prev_url = None
    return _json({
        'resourceType': 'Bundle',
        'type': 'searchset',
        'total': total,
        'link': [
            {'relation': 'self', 'url': request.build_absolute_uri()},
            *([{'relation': 'next', 'url': next_url}] if next_url else []),
            *([{'relation': 'previous', 'url': prev_url}] if prev_url else []),
        ],
        'entry': [{'resource': r} for r in page],
    })


@require_GET
def patient_detail(request, patient_uuid):
    bundle = load_bundle(str(patient_uuid))
    if not bundle:
        raise Http404('Paciente / bundle não encontrado')
    patient = get_patient_resource(bundle)
    counts = count_by_resource_type(bundle)
    return _json({
        'id': str(patient_uuid),
        'patient': patient,
        'bundle_type': bundle.get('type'),
        'resource_counts': dict(sorted(counts.items(), key=lambda x: x[0])),
        'links': {
            'bundle': request.build_absolute_uri(
                reverse('hospital:patient_bundle', kwargs={'patient_uuid': patient_uuid})
            ),
            'resource_types': request.build_absolute_uri(
                reverse('hospital:patient_resource_types', kwargs={'patient_uuid': patient_uuid})
            ),
        },
    })


@require_GET
def patient_bundle(request, patient_uuid):
    bundle = load_bundle(str(patient_uuid))
    if not bundle:
        raise Http404('Bundle não encontrado')
    return _json(bundle)


@require_GET
def patient_resource_types(request, patient_uuid):
    bundle = load_bundle(str(patient_uuid))
    if not bundle:
        raise Http404('Bundle não encontrado')
    counts = count_by_resource_type(bundle)
    types = []
    for rt, n in sorted(counts.items()):
        if rt not in ALLOWED_RESOURCE_TYPES:
            continue
        url = request.build_absolute_uri(
            reverse('hospital:patient_resources', kwargs={'patient_uuid': patient_uuid, 'resource_type': rt})
        )
        types.append({'type': rt, 'count': n, 'url': url})
    return _json({'patient_id': str(patient_uuid), 'types': types})


@require_GET
def patient_resources(request, patient_uuid, resource_type):
    if resource_type not in ALLOWED_RESOURCE_TYPES:
        return _json({'error': f'Tipo não suportado: {resource_type}'}, status=400)
    bundle = load_bundle(str(patient_uuid))
    if not bundle:
        raise Http404('Bundle não encontrado')
    if resource_type == 'Patient':
        p = get_patient_resource(bundle)
        if not p:
            raise Http404('Patient não encontrado no bundle')
        return _json(p)
    items = resources_by_type(bundle, resource_type)
    limit = int(request.GET.get('limit', 200))
    offset = int(request.GET.get('offset', 0))
    page, total = _paginate(items, limit, offset)
    return _json({
        'resourceType': 'Bundle',
        'type': 'searchset',
        'patient': str(patient_uuid),
        'resource_type': resource_type,
        'total': total,
        'entry': [{'resource': r} for r in page],
    })
