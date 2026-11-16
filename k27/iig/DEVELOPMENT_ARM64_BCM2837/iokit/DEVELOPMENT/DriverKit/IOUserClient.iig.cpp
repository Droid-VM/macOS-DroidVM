/* iig(DriverKit-427.100.5 Apr 30 2025 01:57:02) generated from IOUserClient.iig */

#undef	IIG_IMPLEMENTATION
#define	IIG_IMPLEMENTATION 	IOUserClient.iig

#if KERNEL
#include <libkern/c++/OSString.h>
#else
#include <DriverKit/DriverKit.h>
#endif /* KERNEL */
#include <DriverKit/IOReturn.h>
#include <DriverKit/IOUserClient.h>

/* @iig implementation */
#include <DriverKit/IOBufferMemoryDescriptor.h>
/* @iig end */


#if __has_builtin(__builtin_load_member_function_pointer)
#define SimpleMemberFunctionCast(cfnty, self, func) (cfnty)__builtin_load_member_function_pointer(self, func)
#else
#define SimpleMemberFunctionCast(cfnty, self, func) OSMemberFunctionCast(cfnty, &(self), func)
#endif


struct IOUserClient_AsyncCompletion_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  action;
    IOReturn  status;
    const unsigned long long *  asyncData;
#if !defined(__LP64__)
    uint32_t __asyncDataPad;
#endif /* !defined(__LP64__) */
    unsigned long long __asyncData[16];
    uint32_t  asyncDataCount;
};
#pragma pack(4)
struct IOUserClient_AsyncCompletion_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
};
struct IOUserClient_AsyncCompletion_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
    IOUserClient_AsyncCompletion_Msg_Content content;
};
#pragma pack()
#define IOUserClient_AsyncCompletion_Msg_ObjRefs (2)

struct IOUserClient_AsyncCompletion_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IOUserClient_AsyncCompletion_Rpl
{
    IORPCMessageMach           mach;
};
struct IOUserClient_AsyncCompletion_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOUserClient_AsyncCompletion_Rpl_Content content;
};
#pragma pack()
#define IOUserClient_AsyncCompletion_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOUserClient_AsyncCompletion_Msg * message;
#else /* KERNEL */
        const struct IOUserClient_AsyncCompletion_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOUserClient_AsyncCompletion_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOUserClient_AsyncCompletion_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOUserClient_AsyncCompletion_Invocation;
struct IOUserClient_CopyClientMemoryForType_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    uint64_t  type;
};
#pragma pack(4)
struct IOUserClient_CopyClientMemoryForType_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IOUserClient_CopyClientMemoryForType_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IOUserClient_CopyClientMemoryForType_Msg_Content content;
};
#pragma pack()
#define IOUserClient_CopyClientMemoryForType_Msg_ObjRefs (1)

struct IOUserClient_CopyClientMemoryForType_Rpl_Content
{
    IORPCMessage __hdr;
    OSObjectRef  memory;
    unsigned long long  options;
};
#pragma pack(4)
struct IOUserClient_CopyClientMemoryForType_Rpl
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t memory__descriptor;
};
struct IOUserClient_CopyClientMemoryForType_Rpl_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t memory__descriptor;
    IOUserClient_CopyClientMemoryForType_Rpl_Content content;
};
#pragma pack()
#define IOUserClient_CopyClientMemoryForType_Rpl_ObjRefs (1)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOUserClient_CopyClientMemoryForType_Msg * message;
#else /* KERNEL */
        const struct IOUserClient_CopyClientMemoryForType_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOUserClient_CopyClientMemoryForType_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOUserClient_CopyClientMemoryForType_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOUserClient_CopyClientMemoryForType_Invocation;
struct IOUserClient_CreateMemoryDescriptorFromClient_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    uint64_t  memoryDescriptorCreateOptions;
    uint32_t  segmentsCount;
    const IOAddressSegment *  segments;
#if !defined(__LP64__)
    uint32_t __segmentsPad;
#endif /* !defined(__LP64__) */
    IOAddressSegment __segments[32];
};
#pragma pack(4)
struct IOUserClient_CreateMemoryDescriptorFromClient_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IOUserClient_CreateMemoryDescriptorFromClient_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IOUserClient_CreateMemoryDescriptorFromClient_Msg_Content content;
};
#pragma pack()
#define IOUserClient_CreateMemoryDescriptorFromClient_Msg_ObjRefs (1)

struct IOUserClient_CreateMemoryDescriptorFromClient_Rpl_Content
{
    IORPCMessage __hdr;
    OSObjectRef  memory;
};
#pragma pack(4)
struct IOUserClient_CreateMemoryDescriptorFromClient_Rpl
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t memory__descriptor;
};
struct IOUserClient_CreateMemoryDescriptorFromClient_Rpl_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t memory__descriptor;
    IOUserClient_CreateMemoryDescriptorFromClient_Rpl_Content content;
};
#pragma pack()
#define IOUserClient_CreateMemoryDescriptorFromClient_Rpl_ObjRefs (1)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOUserClient_CreateMemoryDescriptorFromClient_Msg * message;
#else /* KERNEL */
        const struct IOUserClient_CreateMemoryDescriptorFromClient_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOUserClient_CreateMemoryDescriptorFromClient_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOUserClient_CreateMemoryDescriptorFromClient_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOUserClient_CreateMemoryDescriptorFromClient_Invocation;
struct IOUserClient_CopyClientEntitlements_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
};
#pragma pack(4)
struct IOUserClient_CopyClientEntitlements_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IOUserClient_CopyClientEntitlements_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IOUserClient_CopyClientEntitlements_Msg_Content content;
};
#pragma pack()
#define IOUserClient_CopyClientEntitlements_Msg_ObjRefs (1)

struct IOUserClient_CopyClientEntitlements_Rpl_Content
{
    IORPCMessage __hdr;
    OSDictionary * entitlements;
#if !defined(__LP64__)
    uint32_t __entitlementsPad;
#endif /* !defined(__LP64__) */
};
#pragma pack(4)
struct IOUserClient_CopyClientEntitlements_Rpl
{
    IORPCMessageMach           mach;
    mach_msg_ool_descriptor_t  entitlements__descriptor;
};
struct IOUserClient_CopyClientEntitlements_Rpl_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_ool_descriptor_t  entitlements__descriptor;
    IOUserClient_CopyClientEntitlements_Rpl_Content content;
};
#pragma pack()
#define IOUserClient_CopyClientEntitlements_Rpl_ObjRefs (1)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOUserClient_CopyClientEntitlements_Msg * message;
#else /* KERNEL */
        const struct IOUserClient_CopyClientEntitlements_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOUserClient_CopyClientEntitlements_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOUserClient_CopyClientEntitlements_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOUserClient_CopyClientEntitlements_Invocation;
struct IOUserClient__ExternalMethod_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSData * structureInput;
#if !defined(__LP64__)
    uint32_t __structureInputPad;
#endif /* !defined(__LP64__) */
    OSObjectRef  structureInputDescriptor;
    OSObjectRef  structureOutputDescriptor;
    OSObjectRef  completion;
    uint64_t  selector;
    const unsigned long long *  scalarInput;
#if !defined(__LP64__)
    uint32_t __scalarInputPad;
#endif /* !defined(__LP64__) */
    unsigned long long __scalarInput[16];
    uint32_t  scalarInputCount;
    unsigned int  scalarOutputCount;
    uint64_t  structureOutputMaximumSize;
};
#pragma pack(4)
struct IOUserClient__ExternalMethod_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_ool_descriptor_t  structureInput__descriptor;
    mach_msg_port_descriptor_t structureInputDescriptor__descriptor;
    mach_msg_port_descriptor_t structureOutputDescriptor__descriptor;
    mach_msg_port_descriptor_t completion__descriptor;
};
struct IOUserClient__ExternalMethod_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_ool_descriptor_t  structureInput__descriptor;
    mach_msg_port_descriptor_t structureInputDescriptor__descriptor;
    mach_msg_port_descriptor_t structureOutputDescriptor__descriptor;
    mach_msg_port_descriptor_t completion__descriptor;
    IOUserClient__ExternalMethod_Msg_Content content;
};
#pragma pack()
#define IOUserClient__ExternalMethod_Msg_ObjRefs (5)

struct IOUserClient__ExternalMethod_Rpl_Content
{
    IORPCMessage __hdr;
    OSData * structureOutput;
#if !defined(__LP64__)
    uint32_t __structureOutputPad;
#endif /* !defined(__LP64__) */
    unsigned long long *  scalarOutput;
#if !defined(__LP64__)
    uint32_t __scalarOutputPad;
#endif /* !defined(__LP64__) */
    unsigned long long __scalarOutput[16];
    unsigned int  scalarOutputCount;
};
#pragma pack(4)
struct IOUserClient__ExternalMethod_Rpl
{
    IORPCMessageMach           mach;
    mach_msg_ool_descriptor_t  structureOutput__descriptor;
};
struct IOUserClient__ExternalMethod_Rpl_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_ool_descriptor_t  structureOutput__descriptor;
    IOUserClient__ExternalMethod_Rpl_Content content;
};
#pragma pack()
#define IOUserClient__ExternalMethod_Rpl_ObjRefs (1)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOUserClient__ExternalMethod_Msg * message;
#else /* KERNEL */
        const struct IOUserClient__ExternalMethod_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOUserClient__ExternalMethod_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOUserClient__ExternalMethod_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOUserClient__ExternalMethod_Invocation;
#if !KERNEL
extern OSMetaClass * gOSContainerMetaClass;
extern OSMetaClass * gOSDataMetaClass;
extern OSMetaClass * gOSNumberMetaClass;
extern OSMetaClass * gOSBooleanMetaClass;
extern OSMetaClass * gOSDictionaryMetaClass;
extern OSMetaClass * gOSArrayMetaClass;
extern OSMetaClass * gOSSetMetaClass;
extern OSMetaClass * gOSOrderedSetMetaClass;
extern OSMetaClass * gIODispatchQueueMetaClass;
extern OSMetaClass * gOSStringMetaClass;
extern OSMetaClass * gIOServiceStateNotificationDispatchSourceMetaClass;
extern OSMetaClass * gIOMemoryMapMetaClass;
extern OSMetaClass * gOSAction_IOUserClient_KernelCompletionMetaClass;
#endif /* !KERNEL */

#if !KERNEL

#define IOUserClient_QueueNames  "" \
    "\037IOUserClientQueueExternalMethod"

#define IOUserClient_MethodNames  "" \
    "\017_ExternalMethod"

#define IOUserClientMetaClass_MethodNames  ""

struct OSClassDescription_IOUserClient_t
{
    OSClassDescription base;
    uint64_t           methodOptions[2 * 1];
    uint64_t           metaMethodOptions[2 * 0];
    char               queueNames[sizeof(IOUserClient_QueueNames)];
    char               methodNames[sizeof(IOUserClient_MethodNames)];
    char               metaMethodNames[sizeof(IOUserClientMetaClass_MethodNames)];
};

const struct OSClassDescription_IOUserClient_t
OSClassDescription_IOUserClient =
{
    .base =
    {
        .descriptionSize         = sizeof(OSClassDescription_IOUserClient_t),
        .name                    = "IOUserClient",
        .superName               = "IOService",
        .methodOptionsSize       = 2 * sizeof(uint64_t) * 1,
        .methodOptionsOffset     = __builtin_offsetof(struct OSClassDescription_IOUserClient_t, methodOptions),
        .metaMethodOptionsSize   = 2 * sizeof(uint64_t) * 0,
        .metaMethodOptionsOffset = __builtin_offsetof(struct OSClassDescription_IOUserClient_t, metaMethodOptions),
        .queueNamesSize       = sizeof(IOUserClient_QueueNames),
        .queueNamesOffset     = __builtin_offsetof(struct OSClassDescription_IOUserClient_t, queueNames),
        .methodNamesSize         = sizeof(IOUserClient_MethodNames),
        .methodNamesOffset       = __builtin_offsetof(struct OSClassDescription_IOUserClient_t, methodNames),
        .metaMethodNamesSize     = sizeof(IOUserClientMetaClass_MethodNames),
        .metaMethodNamesOffset   = __builtin_offsetof(struct OSClassDescription_IOUserClient_t, metaMethodNames),
        .flags                   = 1*kOSClassCanRemote,
        .resv1                   = {0},
    },
    .methodOptions =
    {
        IOUserClient__ExternalMethod_ID,
        0x0000000000000000,
    },
    .metaMethodOptions =
    {
    },
    .queueNames      = IOUserClient_QueueNames,
    .methodNames     = IOUserClient_MethodNames,
    .metaMethodNames = IOUserClientMetaClass_MethodNames,
};

OSMetaClass * gIOUserClientMetaClass;

static kern_return_t
IOUserClient_New(OSMetaClass * instance);

const OSClassLoadInformation
IOUserClient_Class = 
{
    .description       = &OSClassDescription_IOUserClient.base,
    .metaPointer       = &gIOUserClientMetaClass,
    .version           = 1,
    .instanceSize      = sizeof(IOUserClient),

    .resv2             = {0},

    .New               = &IOUserClient_New,
    .resv3             = {0},

};

extern const void * const
gIOUserClient_Declaration;
const void * const
gIOUserClient_Declaration
__attribute__((used,visibility("hidden"),section("__DATA_CONST,__osclassinfo,regular,no_dead_strip"),no_sanitize("address")))
    = &IOUserClient_Class;

static kern_return_t
IOUserClient_New(OSMetaClass * instance)
{
    if (!new(instance) IOUserClientMetaClass) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

kern_return_t
IOUserClientMetaClass::New(OSObject * instance)
{
    if (!new(instance) IOUserClient) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

#endif /* !KERNEL */

#ifdef KERNEL
#define MESSAGE_CONTENT(__field) (messageContent->__field)
#else /* KERNEL */
#define MESSAGE_CONTENT(__field) (message->content.__field)
#endif /* KERNEL */

kern_return_t
IOUserClient::Dispatch(const IORPC rpc)
{
    return _Dispatch(this, rpc);
}

kern_return_t
IOUserClient::_Dispatch(IOUserClient * self, const IORPC rpc)
{
    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {
#if KERNEL
        case IOUserClient_CreateMemoryDescriptorFromClient_ID:
        {
            ret = IOUserClient::CreateMemoryDescriptorFromClient_Invoke(rpc, self, SimpleMemberFunctionCast(IOUserClient::CreateMemoryDescriptorFromClient_Handler, *self, &IOUserClient::CreateMemoryDescriptorFromClient_Impl));
            break;
        }
#endif /* !KERNEL */
        case IOUserClient_CopyClientEntitlements_ID:
        {
            ret = IOUserClient::CopyClientEntitlements_Invoke(rpc, self, SimpleMemberFunctionCast(IOUserClient::CopyClientEntitlements_Handler, *self, &IOUserClient::CopyClientEntitlements_Impl));
            break;
        }
        case IOUserClient__ExternalMethod_ID:
        {
            ret = IOUserClient::_ExternalMethod_Invoke(rpc, self, SimpleMemberFunctionCast(IOUserClient::_ExternalMethod_Handler, *self, &IOUserClient::_ExternalMethod_Impl));
            break;
        }
#if KERNEL
        case IOUserClient_KernelCompletion_ID:
        {
            ret = IOUserClient::AsyncCompletion_Invoke(rpc, self, SimpleMemberFunctionCast(IOUserClient::AsyncCompletion_Handler, *self, &IOUserClient::KernelCompletion_Impl), OSTypeID(OSAction_IOUserClient_KernelCompletion));
            break;
        }
#endif /* !KERNEL */

        default:
            ret = IOService::_Dispatch(self, rpc);
            break;
    }

    return (ret);
}

#if KERNEL
kern_return_t
IOUserClient::MetaClass::Dispatch(const IORPC rpc)
{
#else /* KERNEL */
kern_return_t
IOUserClientMetaClass::Dispatch(const IORPC rpc)
{
#endif /* !KERNEL */

    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {

        default:
            ret = OSMetaClassBase::Dispatch(rpc);
            break;
    }

    return (ret);
}

void
IOUserClient::AsyncCompletion(
        OSAction * action,
        IOReturn status,
        const unsigned long long * asyncData,
        uint32_t asyncDataCount,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOUserClient_AsyncCompletion_Msg_With_Content msg;
    } buf;
    struct IOUserClient_AsyncCompletion_Msg_With_Content * msg = &buf.msg;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 1*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOUserClient_AsyncCompletion_ID;
    msg->content.__object = (OSObjectRef) action;
    msg->content.__hdr.objectRefs = IOUserClient_AsyncCompletion_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 2;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->action__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.action = (OSObjectRef) action;

    msg->content.status = status;

    msg->content.asyncData = NULL;

    if (asyncDataCount > (sizeof(msg->content.__asyncData) / sizeof(msg->content.__asyncData[0]))) return;
    bcopy(asyncData, &msg->content.__asyncData[0], asyncDataCount * sizeof(msg->content.__asyncData[0]));

    msg->content.asyncDataCount = asyncDataCount;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = NULL, .sendSize = sizeof(*msg), .replySize = 0, .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = NULL, .sendSize = sizeof(*msg), .replySize = 0 };
#endif /* KERNEL */
    ret = action->Invoke(rpc);

}

kern_return_t
IOUserClient::CopyClientMemoryForType(
        uint64_t type,
        uint64_t * options,
        IOMemoryDescriptor ** memory,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOUserClient_CopyClientMemoryForType_Msg_With_Content msg;
        struct
        {
            IOUserClient_CopyClientMemoryForType_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOUserClient_CopyClientMemoryForType_Msg_With_Content * msg = &buf.msg;
    struct IOUserClient_CopyClientMemoryForType_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 0*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOUserClient_CopyClientMemoryForType_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOUserClient_CopyClientMemoryForType_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 1;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->content.type = type;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOUserClient_CopyClientMemoryForType_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 1) { ret = kIOReturnIPCError; break; };
            if (IOUserClient_CopyClientMemoryForType_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        if (options) *options = rpl->content.options;
        *memory = OSDynamicCast(IOMemoryDescriptor, (OSObject *) rpl->content.memory);
        if (rpl->content.memory && !*memory) ret = kIOReturnBadArgument;
    }


    return (ret);
}

kern_return_t
IOUserClient::CreateMemoryDescriptorFromClient(
        uint64_t memoryDescriptorCreateOptions,
        uint32_t segmentsCount,
        const IOAddressSegment * segments,
        IOMemoryDescriptor ** memory,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOUserClient_CreateMemoryDescriptorFromClient_Msg_With_Content msg;
        struct
        {
            IOUserClient_CreateMemoryDescriptorFromClient_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOUserClient_CreateMemoryDescriptorFromClient_Msg_With_Content * msg = &buf.msg;
    struct IOUserClient_CreateMemoryDescriptorFromClient_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 0*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOUserClient_CreateMemoryDescriptorFromClient_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOUserClient_CreateMemoryDescriptorFromClient_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 1;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->content.memoryDescriptorCreateOptions = memoryDescriptorCreateOptions;

    msg->content.segmentsCount = segmentsCount;

    msg->content.segments = NULL;

    if (segmentsCount > (sizeof(msg->content.__segments) / sizeof(msg->content.__segments[0]))) return kIOReturnOverrun;
    bcopy(segments, &msg->content.__segments[0], segmentsCount * sizeof(msg->content.__segments[0]));

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOUserClient_CreateMemoryDescriptorFromClient_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 1) { ret = kIOReturnIPCError; break; };
            if (IOUserClient_CreateMemoryDescriptorFromClient_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        *memory = OSDynamicCast(IOMemoryDescriptor, (OSObject *) rpl->content.memory);
        if (rpl->content.memory && !*memory) ret = kIOReturnBadArgument;
    }


    return (ret);
}

kern_return_t
IOUserClient::CopyClientEntitlements(
        OSDictionary ** entitlements,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOUserClient_CopyClientEntitlements_Msg_With_Content msg;
        struct
        {
            IOUserClient_CopyClientEntitlements_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOUserClient_CopyClientEntitlements_Msg_With_Content * msg = &buf.msg;
    struct IOUserClient_CopyClientEntitlements_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 0*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOUserClient_CopyClientEntitlements_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOUserClient_CopyClientEntitlements_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 1;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOUserClient_CopyClientEntitlements_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 1) { ret = kIOReturnIPCError; break; };
            if (IOUserClient_CopyClientEntitlements_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        *entitlements = OSDynamicCast(OSDictionary, (OSObject *) rpl->content.entitlements);
        if (rpl->content.entitlements && !*entitlements) ret = kIOReturnBadArgument;
    }


    return (ret);
}

kern_return_t
IOUserClient::_ExternalMethod(
        uint64_t selector,
        const unsigned long long * scalarInput,
        uint32_t scalarInputCount,
        OSData * structureInput,
        IOMemoryDescriptor * structureInputDescriptor,
        unsigned long long * scalarOutput,
        uint32_t * scalarOutputCount,
        uint64_t structureOutputMaximumSize,
        OSData ** structureOutput,
        IOMemoryDescriptor * structureOutputDescriptor,
        OSAction * completion,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOUserClient__ExternalMethod_Msg_With_Content msg;
        struct
        {
            IOUserClient__ExternalMethod_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOUserClient__ExternalMethod_Msg_With_Content * msg = &buf.msg;
    struct IOUserClient__ExternalMethod_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 0*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOUserClient__ExternalMethod_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOUserClient__ExternalMethod_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 5;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->content.selector = selector;

    msg->content.scalarInput = NULL;

    if (scalarInputCount > (sizeof(msg->content.__scalarInput) / sizeof(msg->content.__scalarInput[0]))) return kIOReturnOverrun;
    bcopy(scalarInput, &msg->content.__scalarInput[0], scalarInputCount * sizeof(msg->content.__scalarInput[0]));

    msg->content.scalarInputCount = scalarInputCount;

    msg->structureInput__descriptor.type = MACH_MSG_OOL_DESCRIPTOR;
    msg->structureInput__descriptor.copy = MACH_MSG_VIRTUAL_COPY;
    msg->structureInput__descriptor.address = (void *) __builtin_offsetof(IOUserClient__ExternalMethod_Msg_Content, structureInput);
    msg->content.structureInput = structureInput;

    msg->structureInputDescriptor__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.structureInputDescriptor = (OSObjectRef) structureInputDescriptor;

    if (*scalarOutputCount > (sizeof(rpl->content.__scalarOutput) / sizeof(rpl->content.__scalarOutput[0]))) return kIOReturnOverrun;
    msg->content.scalarOutputCount = *scalarOutputCount;

    msg->content.structureOutputMaximumSize = structureOutputMaximumSize;

    msg->structureOutputDescriptor__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.structureOutputDescriptor = (OSObjectRef) structureOutputDescriptor;

    msg->completion__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.completion = (OSObjectRef) completion;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOUserClient__ExternalMethod_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 1) { ret = kIOReturnIPCError; break; };
            if (IOUserClient__ExternalMethod_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        if (rpl->content.scalarOutputCount < *scalarOutputCount) *scalarOutputCount = rpl->content.scalarOutputCount;
        bcopy(&rpl->content.__scalarOutput[0], scalarOutput, *scalarOutputCount * sizeof(rpl->content.__scalarOutput[0]));
        *structureOutput = OSDynamicCast(OSData, (OSObject *) rpl->content.structureOutput);
        if (rpl->content.structureOutput && !*structureOutput) ret = kIOReturnBadArgument;
    }


    return (ret);
}

kern_return_t
IOUserClient::CreateActionKernelCompletion(size_t referenceSize, OSAction ** action)
{
    kern_return_t ret;

#if defined(IOKIT_ENABLE_SHARED_PTR)
    OSSharedPtr<OSString>
#else /* defined(IOKIT_ENABLE_SHARED_PTR) */
    OSString *
#endif /* !defined(IOKIT_ENABLE_SHARED_PTR) */
    typeName = OSString::withCString("OSAction_IOUserClient_KernelCompletion");
    if (!typeName) {
        return kIOReturnNoMemory;
    }
    ret = OSAction_IOUserClient_KernelCompletion::CreateWithTypeName(this,
                           IOUserClient_KernelCompletion_ID,
                           IOUserClient_AsyncCompletion_ID,
                           referenceSize,
#if defined(IOKIT_ENABLE_SHARED_PTR)
                           typeName.get(),
#else /* defined(IOKIT_ENABLE_SHARED_PTR) */
                           typeName,
#endif /* !defined(IOKIT_ENABLE_SHARED_PTR) */
                           action);

#if !defined(IOKIT_ENABLE_SHARED_PTR)
    typeName->release();
#endif /* !defined(IOKIT_ENABLE_SHARED_PTR) */
    return (ret);
}

kern_return_t
IOUserClient::AsyncCompletion_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        AsyncCompletion_Handler func)
{
    return IOUserClient::AsyncCompletion_Invoke(_rpc, target, func, NULL);
}

kern_return_t
IOUserClient::AsyncCompletion_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        AsyncCompletion_Handler func,
        const OSMetaClass * targetActionClass)
{
    IOUserClient_AsyncCompletion_Invocation rpc = { _rpc };
    IOUserClient_AsyncCompletion_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOUserClient_AsyncCompletion_Msg *         message = rpc.message;
    const IOUserClient_AsyncCompletion_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOUserClient_AsyncCompletion_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
    OSAction * action;
    uint32_t asyncDataCount = (sizeof(MESSAGE_CONTENT(__asyncData)) / sizeof(MESSAGE_CONTENT(__asyncData[0])));
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wtautological-unsigned-zero-compare"
    if (MESSAGE_CONTENT(asyncDataCount) >= 0 && asyncDataCount > MESSAGE_CONTENT(asyncDataCount)) asyncDataCount = MESSAGE_CONTENT(asyncDataCount);
#pragma clang diagnostic pop

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOUserClient_AsyncCompletion_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOUserClient_AsyncCompletion_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    if (targetActionClass) {
        action = (OSAction *) OSMetaClassBase::safeMetaCast((OSObject *) MESSAGE_CONTENT(action), targetActionClass);
    } else {
        action = OSDynamicCast(OSAction, (OSObject *) MESSAGE_CONTENT(action));
    }
    if (!action && MESSAGE_CONTENT(action)) return (kIOReturnBadArgument);

    (*func)(target,
        action,
        MESSAGE_CONTENT(status),
        &MESSAGE_CONTENT(__asyncData[0]),
        asyncDataCount);


    return (kIOReturnSuccess);
}

kern_return_t
IOUserClient::CopyClientMemoryForType_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        CopyClientMemoryForType_Handler func)
{
    IOUserClient_CopyClientMemoryForType_Invocation rpc = { _rpc };
    IOUserClient_CopyClientMemoryForType_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOUserClient_CopyClientMemoryForType_Msg *         message = rpc.message;
    const IOUserClient_CopyClientMemoryForType_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOUserClient_CopyClientMemoryForType_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOUserClient_CopyClientMemoryForType_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOUserClient_CopyClientMemoryForType_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);

    ret = (*func)(target,
        MESSAGE_CONTENT(type),
        &reply->content.options,
        (IOMemoryDescriptor **)&reply->content.memory);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOUserClient_CopyClientMemoryForType_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 1;
    reply->content.__hdr.objectRefs = IOUserClient_CopyClientMemoryForType_Rpl_ObjRefs;
    reply->memory__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    return (ret);
}

kern_return_t
IOUserClient::CreateMemoryDescriptorFromClient_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        CreateMemoryDescriptorFromClient_Handler func)
{
    IOUserClient_CreateMemoryDescriptorFromClient_Invocation rpc = { _rpc };
    IOUserClient_CreateMemoryDescriptorFromClient_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOUserClient_CreateMemoryDescriptorFromClient_Msg *         message = rpc.message;
    const IOUserClient_CreateMemoryDescriptorFromClient_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOUserClient_CreateMemoryDescriptorFromClient_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    uint32_t segmentsCount = (sizeof(MESSAGE_CONTENT(__segments)) / sizeof(MESSAGE_CONTENT(__segments[0])));
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wtautological-unsigned-zero-compare"
    if (MESSAGE_CONTENT(segmentsCount) >= 0 && segmentsCount > MESSAGE_CONTENT(segmentsCount)) segmentsCount = MESSAGE_CONTENT(segmentsCount);
#pragma clang diagnostic pop

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOUserClient_CreateMemoryDescriptorFromClient_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOUserClient_CreateMemoryDescriptorFromClient_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);

    ret = (*func)(target,
        MESSAGE_CONTENT(memoryDescriptorCreateOptions),
        segmentsCount,
        &MESSAGE_CONTENT(__segments[0]),
        (IOMemoryDescriptor **)&reply->content.memory);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOUserClient_CreateMemoryDescriptorFromClient_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 1;
    reply->content.__hdr.objectRefs = IOUserClient_CreateMemoryDescriptorFromClient_Rpl_ObjRefs;
    reply->memory__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    return (ret);
}

kern_return_t
IOUserClient::CopyClientEntitlements_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        CopyClientEntitlements_Handler func)
{
    IOUserClient_CopyClientEntitlements_Invocation rpc = { _rpc };
    IOUserClient_CopyClientEntitlements_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOUserClient_CopyClientEntitlements_Msg *         message = rpc.message;
    const IOUserClient_CopyClientEntitlements_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOUserClient_CopyClientEntitlements_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOUserClient_CopyClientEntitlements_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOUserClient_CopyClientEntitlements_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);

    ret = (*func)(target,
        &reply->content.entitlements);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOUserClient_CopyClientEntitlements_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 1;
    reply->content.__hdr.objectRefs = IOUserClient_CopyClientEntitlements_Rpl_ObjRefs;
    reply->entitlements__descriptor.type = MACH_MSG_OOL_DESCRIPTOR;
    reply->entitlements__descriptor.copy = MACH_MSG_VIRTUAL_COPY;
    reply->entitlements__descriptor.address = (void *) __builtin_offsetof(IOUserClient_CopyClientEntitlements_Rpl_Content, entitlements);
    reply->entitlements__descriptor.size = 0;

    return (ret);
}

kern_return_t
IOUserClient::_ExternalMethod_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        _ExternalMethod_Handler func)
{
    IOUserClient__ExternalMethod_Invocation rpc = { _rpc };
    IOUserClient__ExternalMethod_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOUserClient__ExternalMethod_Msg *         message = rpc.message;
    const IOUserClient__ExternalMethod_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOUserClient__ExternalMethod_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    uint32_t scalarInputCount = (sizeof(MESSAGE_CONTENT(__scalarInput)) / sizeof(MESSAGE_CONTENT(__scalarInput[0])));
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wtautological-unsigned-zero-compare"
    if (MESSAGE_CONTENT(scalarInputCount) >= 0 && scalarInputCount > MESSAGE_CONTENT(scalarInputCount)) scalarInputCount = MESSAGE_CONTENT(scalarInputCount);
#pragma clang diagnostic pop
    IOMemoryDescriptor * structureInputDescriptor;
    unsigned int scalarOutputCount = (sizeof(reply->content.__scalarOutput) / sizeof(reply->content.__scalarOutput[0]));
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wtautological-unsigned-zero-compare"
    if (MESSAGE_CONTENT(scalarOutputCount) >= 0 && scalarOutputCount > MESSAGE_CONTENT(scalarOutputCount)) scalarOutputCount = MESSAGE_CONTENT(scalarOutputCount);
#pragma clang diagnostic pop
    IOMemoryDescriptor * structureOutputDescriptor;
    OSAction * completion;

    if (5 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOUserClient__ExternalMethod_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOUserClient__ExternalMethod_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    if (((OSObject *) MESSAGE_CONTENT(structureInput)) != NULL && OSDynamicCast(OSData, (OSObject *) MESSAGE_CONTENT(structureInput)) == NULL) { return kIOReturnBadArgument; } 
    structureInputDescriptor = OSDynamicCast(IOMemoryDescriptor, (OSObject *) MESSAGE_CONTENT(structureInputDescriptor));
    if (!structureInputDescriptor && MESSAGE_CONTENT(structureInputDescriptor)) return (kIOReturnBadArgument);
    structureOutputDescriptor = OSDynamicCast(IOMemoryDescriptor, (OSObject *) MESSAGE_CONTENT(structureOutputDescriptor));
    if (!structureOutputDescriptor && MESSAGE_CONTENT(structureOutputDescriptor)) return (kIOReturnBadArgument);
    completion = OSDynamicCast(OSAction, (OSObject *) MESSAGE_CONTENT(completion));
    if (!completion && MESSAGE_CONTENT(completion)) return (kIOReturnBadArgument);

    ret = (*func)(target,
        MESSAGE_CONTENT(selector),
        &MESSAGE_CONTENT(__scalarInput[0]),
        scalarInputCount,
        MESSAGE_CONTENT(structureInput),
        structureInputDescriptor,
        &reply->content.__scalarOutput[0],
        &scalarOutputCount,
        MESSAGE_CONTENT(structureOutputMaximumSize),
        &reply->content.structureOutput,
        structureOutputDescriptor,
        completion);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOUserClient__ExternalMethod_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 1;
    reply->content.__hdr.objectRefs = IOUserClient__ExternalMethod_Rpl_ObjRefs;
    reply->content.scalarOutputCount = scalarOutputCount;
    reply->structureOutput__descriptor.type = MACH_MSG_OOL_DESCRIPTOR;
    reply->structureOutput__descriptor.copy = MACH_MSG_VIRTUAL_COPY;
    reply->structureOutput__descriptor.address = (void *) __builtin_offsetof(IOUserClient__ExternalMethod_Rpl_Content, structureOutput);
    reply->structureOutput__descriptor.size = 0;

    return (ret);
}

#if KERNEL
OSDefineMetaClassAndStructors(OSAction_IOUserClient_KernelCompletion, OSAction);
#endif /* KERNEL */

#if !KERNEL

#define OSAction_IOUserClient_KernelCompletion_QueueNames  ""

#define OSAction_IOUserClient_KernelCompletion_MethodNames  ""

#define OSAction_IOUserClient_KernelCompletionMetaClass_MethodNames  ""

struct OSClassDescription_OSAction_IOUserClient_KernelCompletion_t
{
    OSClassDescription base;
    uint64_t           methodOptions[2 * 0];
    uint64_t           metaMethodOptions[2 * 0];
    char               queueNames[sizeof(OSAction_IOUserClient_KernelCompletion_QueueNames)];
    char               methodNames[sizeof(OSAction_IOUserClient_KernelCompletion_MethodNames)];
    char               metaMethodNames[sizeof(OSAction_IOUserClient_KernelCompletionMetaClass_MethodNames)];
};

 __attribute__((availability(driverkit,introduced=20,message="Type-safe OSAction factory methods are available in DriverKit 20 and newer")))
const struct OSClassDescription_OSAction_IOUserClient_KernelCompletion_t
OSClassDescription_OSAction_IOUserClient_KernelCompletion =
{
    .base =
    {
        .descriptionSize         = sizeof(OSClassDescription_OSAction_IOUserClient_KernelCompletion_t),
        .name                    = "OSAction_IOUserClient_KernelCompletion",
        .superName               = "OSAction",
        .methodOptionsSize       = 2 * sizeof(uint64_t) * 0,
        .methodOptionsOffset     = __builtin_offsetof(struct OSClassDescription_OSAction_IOUserClient_KernelCompletion_t, methodOptions),
        .metaMethodOptionsSize   = 2 * sizeof(uint64_t) * 0,
        .metaMethodOptionsOffset = __builtin_offsetof(struct OSClassDescription_OSAction_IOUserClient_KernelCompletion_t, metaMethodOptions),
        .queueNamesSize       = sizeof(OSAction_IOUserClient_KernelCompletion_QueueNames),
        .queueNamesOffset     = __builtin_offsetof(struct OSClassDescription_OSAction_IOUserClient_KernelCompletion_t, queueNames),
        .methodNamesSize         = sizeof(OSAction_IOUserClient_KernelCompletion_MethodNames),
        .methodNamesOffset       = __builtin_offsetof(struct OSClassDescription_OSAction_IOUserClient_KernelCompletion_t, methodNames),
        .metaMethodNamesSize     = sizeof(OSAction_IOUserClient_KernelCompletionMetaClass_MethodNames),
        .metaMethodNamesOffset   = __builtin_offsetof(struct OSClassDescription_OSAction_IOUserClient_KernelCompletion_t, metaMethodNames),
        .flags                   = 0*kOSClassCanRemote,
        .resv1                   = {0},
    },
    .methodOptions =
    {
    },
    .metaMethodOptions =
    {
    },
    .queueNames      = OSAction_IOUserClient_KernelCompletion_QueueNames,
    .methodNames     = OSAction_IOUserClient_KernelCompletion_MethodNames,
    .metaMethodNames = OSAction_IOUserClient_KernelCompletionMetaClass_MethodNames,
};

 __attribute__((availability(driverkit,introduced=20,message="Type-safe OSAction factory methods are available in DriverKit 20 and newer")))
OSMetaClass * gOSAction_IOUserClient_KernelCompletionMetaClass;

 __attribute__((availability(driverkit,introduced=20,message="Type-safe OSAction factory methods are available in DriverKit 20 and newer")))
static kern_return_t
OSAction_IOUserClient_KernelCompletion_New(OSMetaClass * instance);

 __attribute__((availability(driverkit,introduced=20,message="Type-safe OSAction factory methods are available in DriverKit 20 and newer")))
const OSClassLoadInformation
OSAction_IOUserClient_KernelCompletion_Class = 
{
    .description       = &OSClassDescription_OSAction_IOUserClient_KernelCompletion.base,
    .metaPointer       = &gOSAction_IOUserClient_KernelCompletionMetaClass,
    .version           = 1,
    .instanceSize      = sizeof(OSAction_IOUserClient_KernelCompletion),

    .resv2             = {0},

    .New               = &OSAction_IOUserClient_KernelCompletion_New,
    .resv3             = {0},

};

 __attribute__((availability(driverkit,introduced=20,message="Type-safe OSAction factory methods are available in DriverKit 20 and newer")))
extern const void * const
gOSAction_IOUserClient_KernelCompletion_Declaration;
 __attribute__((availability(driverkit,introduced=20,message="Type-safe OSAction factory methods are available in DriverKit 20 and newer")))
const void * const
gOSAction_IOUserClient_KernelCompletion_Declaration
 __attribute__((availability(driverkit,introduced=20,message="Type-safe OSAction factory methods are available in DriverKit 20 and newer")))
__attribute__((used,visibility("hidden"),section("__DATA_CONST,__osclassinfo,regular,no_dead_strip"),no_sanitize("address")))
    = &OSAction_IOUserClient_KernelCompletion_Class;

 __attribute__((availability(driverkit,introduced=20,message="Type-safe OSAction factory methods are available in DriverKit 20 and newer")))
static kern_return_t
OSAction_IOUserClient_KernelCompletion_New(OSMetaClass * instance)
{
    if (!new(instance) OSAction_IOUserClient_KernelCompletionMetaClass) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

 __attribute__((availability(driverkit,introduced=20,message="Type-safe OSAction factory methods are available in DriverKit 20 and newer")))
kern_return_t
OSAction_IOUserClient_KernelCompletionMetaClass::New(OSObject * instance)
{
    if (!new(instance) OSAction_IOUserClient_KernelCompletion) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

#endif /* !KERNEL */

#ifdef KERNEL
#define MESSAGE_CONTENT(__field) (messageContent->__field)
#else /* KERNEL */
#define MESSAGE_CONTENT(__field) (message->content.__field)
#endif /* KERNEL */

kern_return_t
OSAction_IOUserClient_KernelCompletion::Dispatch(const IORPC rpc)
{
    return _Dispatch(this, rpc);
}

kern_return_t
OSAction_IOUserClient_KernelCompletion::_Dispatch(OSAction_IOUserClient_KernelCompletion * self, const IORPC rpc)
{
    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {

        default:
            ret = OSAction::_Dispatch(self, rpc);
            break;
    }

    return (ret);
}

#if KERNEL
kern_return_t
OSAction_IOUserClient_KernelCompletion::MetaClass::Dispatch(const IORPC rpc)
{
#else /* KERNEL */
kern_return_t
OSAction_IOUserClient_KernelCompletionMetaClass::Dispatch(const IORPC rpc)
{
#endif /* !KERNEL */

    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {

        default:
            ret = OSMetaClassBase::Dispatch(rpc);
            break;
    }

    return (ret);
}



